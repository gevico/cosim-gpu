// SPDX-License-Identifier: Apache-2.0

//! Session execution: resource ownership, node supervision and verdicts.

use std::fs;
use std::io::Write;
use std::os::fd::{AsFd, BorrowedFd};
use std::path::{Path, PathBuf};
use std::time::Duration;

use anyhow::{Context, Result, ensure};
use cosim_topology::DiskMode;
use futures_util::StreamExt;
use futures_util::future;
use futures_util::stream::FuturesUnordered;
use serde::{Deserialize, Serialize};
use tokio::sync::mpsc;
use tokio::time::{self, Instant};
use tokio_util::sync::CancellationToken;

use crate::disk::{self, DiskResources, Helpers, Protected};
use crate::layout::SessionLayout;
use crate::manifest::{self, Manifest};
use crate::node::{self, NodeContext};
use crate::plan::{self, NodeRole, Plan};
use crate::process::{self, Lifeline};
use crate::resource::{self, FileId, NewDir, OwnedDir, OwnedFile, RunLock};

/// Validated deadlines and tools for one run.
///
/// The fields are private so that every value passes [`RunOptions::new`].
#[derive(Clone, Debug, Serialize)]
pub struct RunOptions {
    /// Time each process has to pass its readiness probes.
    ready_timeout: Duration,
    /// Run duration after every process is ready.
    run_for: Option<Duration>,
    /// `qemu-img` executable, absolute or searched in the plan's `PATH`.
    qemu_img: String,
}

impl RunOptions {
    /// Validates limits before any resource is allocated.
    pub fn new(
        ready_timeout: Duration,
        run_for: Option<Duration>,
        qemu_img: String,
    ) -> Result<Self> {
        ensure!(
            !ready_timeout.is_zero() && ready_timeout <= Duration::from_secs(86_400),
            "the readiness timeout must be positive and at most one day"
        );
        ensure!(
            run_for.is_none_or(|duration| {
                !duration.is_zero() && duration <= Duration::from_secs(31_536_000)
            }),
            "the run duration must be positive and at most one year"
        );
        ensure!(!qemu_img.is_empty(), "a qemu-img executable is required");
        let qemu_img = if qemu_img.contains('/') {
            std::path::absolute(&qemu_img)?
                .to_str()
                .context("the qemu-img path must be valid UTF-8")?
                .to_owned()
        } else {
            qemu_img
        };
        Ok(Self {
            ready_timeout,
            run_for,
            qemu_img,
        })
    }
}

/// Requests that end a session.
///
/// `graceful` stops processes in reverse dependency order; `force` also
/// skips remaining grace periods.
#[derive(Clone, Debug, Default)]
pub struct Shutdown {
    /// Starts graceful shutdown.
    pub graceful: CancellationToken,
    /// Skips grace periods during shutdown.
    pub force: CancellationToken,
}

/// Progress reported while a session runs.
#[non_exhaustive]
#[derive(Clone, Debug)]
pub enum Event {
    /// A process started.
    Started {
        /// Process identifier.
        process: String,
    },
    /// A process passed its readiness probes.
    Ready {
        /// Process identifier.
        process: String,
    },
    /// A process exited on its own.
    Exited {
        /// Process identifier.
        process: String,
        /// Exit status.
        status: String,
    },
    /// A process and its sockets are gone.
    Stopped {
        /// Process identifier.
        process: String,
    },
}

/// Session outcome.
#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum Status {
    /// Every process stopped as requested and cleanup succeeded.
    Pass,
    /// A process or cleanup step failed.
    Fail,
}

/// The final result, also written to `verdict.json`.
#[non_exhaustive]
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Verdict {
    /// Session outcome.
    pub status: Status,
    /// First failure, when any.
    pub reason: Option<String>,
    /// Failures while removing session resources.
    pub cleanup_errors: Vec<String>,
    /// Whether every owned process is known to have exited.
    pub users_stopped: bool,
}

/// Runs a plan until its hosts exit, `run_for` elapses or shutdown is requested.
///
/// Errors before the run directory exists are returned; later failures are
/// reported in the verdict after resources are released.
pub async fn run(
    plan: &Plan,
    options: &RunOptions,
    shutdown: &Shutdown,
    events: mpsc::UnboundedSender<Event>,
) -> Result<Verdict> {
    let preflight = preflight(plan, options)?;
    let mut session = Session::create(plan, options)?;
    let stop = Shutdown {
        graceful: shutdown.graceful.child_token(),
        force: shutdown.force.clone(),
    };
    let mut failures = Failures::default();
    let prepared = session.prepare(plan, options, &preflight, &stop).await;
    failures.record(prepared);
    if failures.is_empty() && !stop.graceful.is_cancelled() {
        let inherited = session.inherited(plan);
        supervise(
            plan,
            options,
            &preflight.lifeline,
            &inherited,
            &stop,
            &events,
            &mut failures,
        )
        .await;
    }
    Ok(session.finish(failures))
}

/// Executables resolved before the session creates resources.
struct Preflight {
    lifeline: Lifeline,
    qemu_img: Option<PathBuf>,
}

fn preflight(plan: &Plan, options: &RunOptions) -> Result<Preflight> {
    for machine in &plan.machines {
        if let Some(agent) = &machine.placement {
            anyhow::bail!(
                "machine {} is placed on {agent}; remote agents are not supported",
                machine.id
            );
        }
    }
    let lifeline = Lifeline::locate(&plan.env.search_path)?;
    for process in &plan.processes {
        ensure!(
            plan::executable(&process.program),
            "executable is unavailable: {}",
            process.program.display()
        );
    }
    let needs_helper = plan
        .machines
        .iter()
        .flat_map(|machine| &machine.disks)
        .any(|disk| disk.create.is_some() || disk.mode == DiskMode::Overlay);
    let qemu_img = needs_helper
        .then(|| plan::resolve_program(&options.qemu_img, &plan.env.search_path))
        .transpose()
        .context("disk preparation requires qemu-img")?;
    if let Some(program) = &qemu_img {
        ensure!(
            plan::executable(program),
            "qemu-img executable is unavailable: {}",
            program.display()
        );
    }
    Ok(Preflight { lifeline, qemu_img })
}

/// Failures collected while a session runs.
#[derive(Default)]
struct Failures {
    errors: Vec<anyhow::Error>,
    unconfirmed: bool,
}

impl Failures {
    fn record(&mut self, result: Result<()>) {
        if let Err(error) = result {
            self.unconfirmed |= process::unconfirmed(&error);
            self.errors.push(error);
        }
    }

    fn is_empty(&self) -> bool {
        self.errors.is_empty()
    }
}

/// Starts every process and waits for all of them to stop.
///
/// `inherited` lists the lock descriptors of each process in plan order.
async fn supervise(
    plan: &Plan,
    options: &RunOptions,
    lifeline: &Lifeline,
    inherited: &[Vec<BorrowedFd<'_>>],
    stop: &Shutdown,
    events: &mpsc::UnboundedSender<Event>,
    failures: &mut Failures,
) {
    let cancel = &stop.graceful;
    let (ready_sender, mut ready) = mpsc::unbounded_channel();
    let context = NodeContext {
        lifeline,
        ready_timeout: options.ready_timeout,
        cancel,
        force: &stop.force,
        events,
        ready: &ready_sender,
    };
    let links = match node::links(&plan.processes) {
        Ok(links) => links,
        Err(error) => return failures.record(Err(error)),
    };
    let mut nodes = plan
        .processes
        .iter()
        .zip(links)
        .zip(inherited)
        .map(|((process, links), inherit)| node::run(process, links, inherit, &context))
        .collect::<FuturesUnordered<_>>();
    let mut ready_count = 0;
    let mut deadline = None;
    loop {
        let expired = async {
            match deadline {
                Some(deadline) => time::sleep_until(deadline).await,
                None => future::pending().await,
            }
        };
        tokio::select! {
            end = nodes.next() => {
                let Some(end) = end else { break };
                failures.unconfirmed |= !end.stopped;
                if end.result.is_err() {
                    cancel.cancel();
                }
                failures.record(end.result);
            }
            Some(()) = ready.recv() => {
                ready_count += 1;
                if ready_count == plan.processes.len() {
                    deadline = options.run_for.map(|duration| Instant::now() + duration);
                }
            }
            () = expired => {
                deadline = None;
                cancel.cancel();
            }
        }
    }
}

/// Resources of one machine.
///
/// [`MachineResources::release`] removes overlays and releases leases before
/// the pool file and its directory are removed.
struct MachineResources {
    disks: DiskResources,
    pool: OwnedFile,
    pool_parent: OwnedDir,
}

impl MachineResources {
    fn release(self, errors: &mut Vec<String>) {
        let Self {
            disks,
            pool,
            pool_parent,
        } = self;
        errors.extend(disks.release().iter().map(|error| format!("{error:#}")));
        push_error(errors, pool.remove());
        push_error(errors, pool_parent.remove());
    }
}

/// Everything a running session owns.
///
/// Process groups are owned by their nodes. Files are released explicitly by
/// [`Session::finish`] after their users stop; dropping a session releases
/// only its locks and leaves the files to `cosim clean`.
struct Session {
    machines: Vec<MachineResources>,
    lock: RunLock,
    layout: SessionLayout,
    token: String,
}

impl Session {
    /// Creates the run directory, its lock and metadata, and the pool directory.
    fn create(plan: &Plan, options: &RunOptions) -> Result<Self> {
        let layout = &plan.layout;
        let token = uuid::Uuid::new_v4().simple().to_string();
        let run_dir = NewDir::create(&layout.run_staging(&token))?;
        let staged = SessionLayout {
            run_dir: run_dir.path().to_path_buf(),
            ..layout.clone()
        };
        let lock = RunLock::create(&staged.lock())?;
        write_json(&staged.manifest(), &Manifest::new(plan, &token)?)?;
        write_json(&staged.plan(), plan)?;
        write_json(&staged.options(), options)?;
        // Recovery metadata and its held lock become visible together,
        // before the session creates resources outside this directory.
        let run_dir = run_dir.publish(&layout.run_dir)?;
        // The pool directory appears under its name only with the ownership
        // marker inside, so `cosim clean` of another session never takes it
        // for its own.
        let pool_dir = NewDir::create(&layout.pool_staging(&token))?;
        resource::new_file(&SessionLayout::marker_in(pool_dir.path()))?
            .write_all(token.as_bytes())
            .context("write the pool ownership marker")?;
        let pool_dir = pool_dir.publish(&layout.pool_dir)?;
        pool_dir.commit();
        run_dir.commit();
        Ok(Self {
            machines: Vec::new(),
            lock,
            layout: layout.clone(),
            token,
        })
    }

    /// Creates memory pools and prepares disks, machine by machine.
    ///
    /// Cancellation stops preparation without an error.
    async fn prepare(
        &mut self,
        plan: &Plan,
        options: &RunOptions,
        preflight: &Preflight,
        stop: &Shutdown,
    ) -> Result<()> {
        let cancel = &stop.graceful;
        let total = plan.machines.iter().try_fold(0u64, |total, machine| {
            total
                .checked_add(machine.memory.size)
                .context("total memory overflow")
        })?;
        let statistics = nix::sys::statvfs::statvfs(&self.layout.pool_dir)
            .with_context(|| format!("inspect {}", self.layout.pool_dir.display()))?;
        let available =
            widen(statistics.blocks_available()).saturating_mul(widen(statistics.fragment_size()));
        ensure!(
            available >= total,
            "insufficient shared-memory capacity in {}: need {total} bytes, {available} available",
            self.layout.pool_dir.display()
        );
        let mut protected = Protected {
            directories: vec![
                FileId::of(&self.layout.run_dir)?,
                FileId::of(&self.layout.pool_dir)?,
            ],
            files: Vec::new(),
        };
        let qemu_img = preflight.qemu_img.as_deref();
        let helper_env = [
            ("PATH".to_owned(), plan.env.search_path.clone()),
            ("LANG".to_owned(), "C".to_owned()),
        ]
        .into();
        for machine in &plan.machines {
            if cancel.is_cancelled() {
                return Ok(());
            }
            let machine_dir = self.layout.machine_dir(&machine.id);
            fs::create_dir_all(&machine_dir)
                .with_context(|| format!("create {}", machine_dir.display()))?;
            write_json(&self.layout.memory_record(&machine.id), &machine.memory)?;
            let pool_parent = OwnedDir::create(
                machine
                    .pool
                    .parent()
                    .context("the pool file has no parent directory")?,
            )?;
            let (pool, file) = match OwnedFile::create(&machine.pool) {
                Ok(created) => created,
                Err(error) => {
                    // A directory left behind is still removed by `cosim clean`.
                    let _ = pool_parent.remove();
                    return Err(error);
                }
            };
            let mut resources = MachineResources {
                disks: DiskResources::default(),
                pool,
                pool_parent,
            };
            let prepared = async {
                resource::reserve(&file, machine.memory.size)
                    .with_context(|| format!("reserve {}", machine.pool.display()))?;
                protected.files.push(FileId::of(&machine.pool)?);
                for disk in &machine.disks {
                    if cancel.is_cancelled() {
                        break;
                    }
                    let helpers = Helpers {
                        qemu_img,
                        env: &helper_env,
                        lifeline: &preflight.lifeline,
                        lock: self.lock.as_fd(),
                        timeout: options.ready_timeout,
                        cancel,
                        force: &stop.force,
                        lock_dir: &plan.env.disk_lock_dir,
                        token: &self.token,
                    };
                    disk::prepare(disk, &helpers, &protected, &mut resources.disks).await?;
                }
                anyhow::Ok(())
            }
            .await;
            self.machines.push(resources);
            prepared.with_context(|| format!("machine {}", machine.id))?;
        }
        Ok(())
    }

    /// Lock descriptors each process keeps, in plan order: the session lock,
    /// and for a vHost also the image leases of its machine.
    fn inherited(&self, plan: &Plan) -> Vec<Vec<BorrowedFd<'_>>> {
        plan.processes
            .iter()
            .map(|process| {
                let mut descriptors = vec![self.lock.as_fd()];
                if process.role == NodeRole::Vhost
                    && let Some(machine) = self.machines.get(process.machine)
                {
                    descriptors.extend(machine.disks.leases());
                }
                descriptors
            })
            .collect()
    }

    /// Releases resources when their users stopped, then writes the verdict.
    ///
    /// When termination is unconfirmed, files stay for `cosim clean`, which
    /// waits for the inherited session lock.
    fn finish(self, failures: Failures) -> Verdict {
        let Self {
            machines,
            lock,
            layout,
            token,
        } = self;
        let users_stopped = !failures.unconfirmed;
        let mut cleanup_errors = Vec::new();
        if users_stopped {
            for machine in machines {
                machine.release(&mut cleanup_errors);
            }
            // The marker stays while owned pool files remain, so `cosim clean`
            // can retry after the filesystem problem is fixed.
            if cleanup_errors.is_empty() {
                push_error(
                    &mut cleanup_errors,
                    manifest::remove_pool_dir(&layout, &token),
                );
            }
        }
        let reason = (!failures.errors.is_empty()).then(|| {
            failures
                .errors
                .iter()
                .map(|error| format!("{error:#}"))
                .collect::<Vec<_>>()
                .join("; ")
        });
        let status = if reason.is_none() && cleanup_errors.is_empty() {
            Status::Pass
        } else {
            Status::Fail
        };
        let mut verdict = Verdict {
            status,
            reason,
            cleanup_errors,
            users_stopped,
        };
        if let Err(error) = write_json(&layout.verdict(), &verdict) {
            verdict.status = Status::Fail;
            verdict.cleanup_errors.push(format!("{error:#}"));
        }
        drop(lock);
        verdict
    }
}

fn push_error(errors: &mut Vec<String>, result: Result<()>) {
    if let Err(error) = result {
        errors.push(format!("{error:#}"));
    }
}

/// Converts filesystem counters whose width differs between platforms.
fn widen(value: impl Into<u64>) -> u64 {
    value.into()
}

/// Writes pretty-printed JSON to a new or existing file.
pub(crate) fn write_json(path: &Path, value: &impl Serialize) -> Result<()> {
    let text = serde_json::to_vec_pretty(value)?;
    fs::write(path, text).with_context(|| format!("write {}", path.display()))
}

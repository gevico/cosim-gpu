// SPDX-License-Identifier: Apache-2.0

//! Disk images prepared for a vHost: creation, leases and overlays.

use std::collections::BTreeMap;
use std::fs;
use std::io::ErrorKind;
use std::os::fd::{AsFd, BorrowedFd};
use std::path::Path;
use std::time::Duration;

use anyhow::{Context, Result, bail, ensure};
use cosim_topology::{ByteSize, DiskMode};
use tokio::time;
use tokio_util::sync::CancellationToken;

use crate::layout::SessionLayout;
use crate::plan::DiskPlan;
use crate::process::{self, Lifeline, ProcessGroup, Spawn};
use crate::resource::{DiskLease, FileId, LeaseKind, OwnedFile};

/// Tools and limits for image helpers.
pub(crate) struct Helpers<'a> {
    /// `qemu-img`, resolved when a disk needs creation or an overlay.
    pub(crate) qemu_img: Option<&'a Path>,
    pub(crate) env: &'a BTreeMap<String, String>,
    pub(crate) lifeline: &'a Lifeline,
    /// Session lock, kept by every helper so that `cosim clean` waits for it.
    pub(crate) lock: BorrowedFd<'a>,
    pub(crate) timeout: Duration,
    pub(crate) cancel: &'a CancellationToken,
    pub(crate) force: &'a CancellationToken,
    pub(crate) lock_dir: &'a Path,
    /// Session token that names temporary images.
    pub(crate) token: &'a str,
}

/// How an image helper ended without failing.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Outcome {
    /// The helper completed its operation.
    Finished,
    /// Session cancellation stopped the helper or prevented its start.
    Cancelled,
}

/// Session-owned files and directories that disk sources must not alias.
pub(crate) struct Protected {
    pub(crate) directories: Vec<FileId>,
    pub(crate) files: Vec<FileId>,
}

/// The overlays and image leases of one machine.
///
/// Dropping the value releases the leases and leaves the overlays for
/// `cosim clean`.
#[derive(Default)]
pub(crate) struct DiskResources {
    overlays: Vec<OwnedFile>,
    leases: Vec<DiskLease>,
}

impl DiskResources {
    /// Lock descriptors of the image leases.
    pub(crate) fn leases(&self) -> impl Iterator<Item = BorrowedFd<'_>> {
        self.leases.iter().map(AsFd::as_fd)
    }

    /// Removes the overlays, then releases the image leases.
    pub(crate) fn release(self) -> Vec<anyhow::Error> {
        let Self { overlays, leases } = self;
        let errors = overlays
            .into_iter()
            .filter_map(|overlay| overlay.remove().err())
            .collect();
        drop(leases);
        errors
    }
}

/// Creates a missing source, locks the image and creates the session overlay.
///
/// Each lease and overlay is registered in `resources` before the next
/// fallible step, so the caller decides when to release it. Cancellation
/// stops preparation without an error.
pub(crate) async fn prepare(
    disk: &DiskPlan,
    helpers: &Helpers<'_>,
    protected: &Protected,
    resources: &mut DiskResources,
) -> Result<()> {
    let prepare = async {
        match fs::metadata(&disk.source) {
            Ok(metadata) => ensure!(
                metadata.is_file(),
                "disk source is not a regular file: {}",
                disk.source.display()
            ),
            Err(error) if error.kind() == ErrorKind::NotFound => match disk.create {
                Some(size) => {
                    if create(disk, size, helpers).await? == Outcome::Cancelled {
                        return Ok(());
                    }
                }
                None => bail!("missing disk {}", disk.source.display()),
            },
            Err(error) => {
                return Err(error).with_context(|| format!("inspect {}", disk.source.display()));
            }
        }
        let source = fs::canonicalize(&disk.source)
            .with_context(|| format!("resolve {}", disk.source.display()))?;
        let image = FileId::of(&source)?;
        ensure!(
            !protected.files.contains(&image),
            "disk source {} is a session memory pool",
            disk.source.display()
        );
        for ancestor in source.ancestors().skip(1) {
            ensure!(
                !protected.directories.contains(&FileId::of(ancestor)?),
                "disk source {} is inside a session directory",
                disk.source.display()
            );
        }
        let kind = match disk.mode {
            DiskMode::Direct => LeaseKind::Exclusive,
            DiskMode::ReadOnly | DiskMode::Overlay => LeaseKind::Shared,
        };
        let lease = DiskLease::acquire(helpers.lock_dir, image, kind)
            .with_context(|| format!("lock {}", disk.source.display()))?;
        resources.leases.push(lease);
        if disk.mode == DiskMode::Overlay {
            ensure!(
                !disk.target.exists(),
                "overlay already exists: {}",
                disk.target.display()
            );
            resources
                .overlays
                .push(OwnedFile::adopt(disk.target.clone()));
            let backing = path_text(&source)?;
            let target = path_text(&disk.target)?;
            let format = disk.source_format.as_str();
            // The helper keeps the backing lease while it reads the image. A
            // cancelled overlay is removed with the other overlays.
            run_helper(
                &["create", "-f", "qcow2", "-F", format, "-b", backing, target],
                disk,
                helpers,
                resources.leases.last().map(AsFd::as_fd),
            )
            .await?;
        }
        Ok(())
    };
    prepare.await.with_context(|| format!("disk {}", disk.id))
}

/// Formats a temporary image and publishes it with a link that never replaces
/// an image created concurrently by another session.
async fn create(disk: &DiskPlan, size: ByteSize, helpers: &Helpers<'_>) -> Result<Outcome> {
    let parent = disk
        .source
        .parent()
        .context("the disk source has no parent directory")?;
    ensure!(
        parent.is_dir(),
        "disk parent directory does not exist: {}",
        parent.display()
    );
    let temporary = SessionLayout::temporary_image(&disk.source, helpers.token)?;
    let (image, _) = OwnedFile::create(&temporary)?;
    let size = size.to_string();
    let format = disk.source_format.as_str();
    let formatted = run_helper(
        &["create", "-f", format, path_text(&temporary)?, &size],
        disk,
        helpers,
        None,
    )
    .await;
    match formatted {
        Ok(Outcome::Finished) => {}
        Ok(Outcome::Cancelled) => {
            image.remove().context("remove the unfinished image")?;
            return Ok(Outcome::Cancelled);
        }
        Err(error) => {
            // An unconfirmed helper may still write the image; `cosim clean`
            // removes it later.
            if !process::unconfirmed(&error) {
                image.remove().context("remove the unfinished image")?;
            }
            return Err(error);
        }
    }
    let published = match fs::hard_link(&temporary, &disk.source) {
        Ok(()) => Ok(()),
        Err(error) if error.kind() == ErrorKind::AlreadyExists => Ok(()),
        Err(error) => Err(error).with_context(|| format!("publish {}", disk.source.display())),
    };
    let removed = image.remove();
    published.and(removed).map(|()| Outcome::Finished)
}

/// Runs `qemu-img` with a deadline and owns it until it has stopped.
///
/// The helper keeps the session lock and, when given, the lease of the image
/// it reads.
async fn run_helper(
    args: &[&str],
    disk: &DiskPlan,
    helpers: &Helpers<'_>,
    lease: Option<BorrowedFd<'_>>,
) -> Result<Outcome> {
    if helpers.cancel.is_cancelled() {
        return Ok(Outcome::Cancelled);
    }
    let qemu_img = helpers
        .qemu_img
        .context("disk preparation requires qemu-img")?;
    let directory = disk.log.parent().context("the helper log has no parent")?;
    let argv = args.iter().map(|arg| (*arg).to_owned()).collect::<Vec<_>>();
    let inherit = std::iter::once(helpers.lock)
        .chain(lease)
        .collect::<Vec<_>>();
    let mut process = ProcessGroup::spawn(
        helpers.lifeline,
        &Spawn {
            program: qemu_img,
            argv: &argv,
            env: helpers.env,
            directory,
            log: &disk.log,
            inherit: &inherit,
        },
    )?;
    let outcome = tokio::select! {
        status = time::timeout(helpers.timeout, process.wait()) => Some(status),
        _ = helpers.cancel.cancelled() => None,
    };
    process.shutdown(helpers.force).await?;
    let log = disk.log.display();
    match outcome {
        Some(Ok(Ok(status))) if status.success() => Ok(Outcome::Finished),
        Some(Ok(Ok(status))) => bail!("qemu-img failed with {status}; see {log}"),
        Some(Ok(Err(error))) => Err(error),
        Some(Err(_)) => bail!("qemu-img timed out; see {log}"),
        None => Ok(Outcome::Cancelled),
    }
}

fn path_text(path: &Path) -> Result<&str> {
    path.to_str()
        .with_context(|| format!("path is not valid UTF-8: {}", path.display()))
}

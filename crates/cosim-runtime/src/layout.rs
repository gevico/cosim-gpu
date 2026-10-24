// SPDX-License-Identifier: Apache-2.0

//! Names of every directory and file a session creates.

use std::fs;
use std::hash::{DefaultHasher, Hash, Hasher};
use std::path::{Component, Path, PathBuf};

use anyhow::{Context, Result, ensure};
use cosim_topology::{Identifier, Topology};
use serde::{Deserialize, Serialize};

/// Session paths derived from a run directory and a pool directory.
///
/// The run directory keeps metadata, sockets, overlays and logs. The pool
/// directory holds one shared-memory file per machine.
#[non_exhaustive]
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct SessionLayout {
    /// Directory that keeps metadata, sockets, overlays and logs.
    pub run_dir: PathBuf,
    /// Directory that holds machine memory pools.
    pub pool_dir: PathBuf,
}

const POOL_SUBDIRECTORY: &str = "memory";
const POOL_MARKER: &str = "owner.token";
const POOL_STAGING_SUFFIX: &str = ".cosim-pool";
const RUN_STAGING_SUFFIX: &str = ".cosim-run";
const OUTPUT_LOG: &str = "output.log";
const TEMPORARY_SUFFIX: &str = ".cosim-new";

impl SessionLayout {
    /// Accepts a new run directory and a pool directory outside it, or the
    /// `memory` subdirectory of the run directory.
    ///
    /// Both paths are resolved against the filesystem first, so the
    /// containment checks hold through symbolic links.
    pub fn new(run_dir: &Path, pool_dir: &Path) -> Result<Self> {
        let run_dir = resolve(run_dir)?;
        let pool_dir = resolve(pool_dir)?;
        ensure!(
            run_dir.to_str().is_some() && pool_dir.to_str().is_some(),
            "session paths must be valid UTF-8"
        );
        ensure!(
            run_dir.file_name().is_some() && pool_dir.file_name().is_some(),
            "the run and pool directories must name new directories"
        );
        ensure!(
            !run_dir.starts_with(&pool_dir),
            "the pool directory must not contain the run directory"
        );
        ensure!(
            !pool_dir.starts_with(&run_dir) || pool_dir == run_dir.join(POOL_SUBDIRECTORY),
            "a pool directory inside the run directory must be its {POOL_SUBDIRECTORY} subdirectory"
        );
        Ok(Self { run_dir, pool_dir })
    }

    /// Returns the default pool directory for a run directory on this system.
    ///
    /// Linux uses `/dev/shm/cosim-<name>-<hash>`, where the hash identifies the
    /// absolute run directory, so run directories with the same name do not
    /// share a pool. Other systems use the `memory` subdirectory.
    pub fn default_pool_dir(run_dir: &Path) -> Result<PathBuf> {
        let run_dir = resolve(run_dir)?;
        let name = run_dir
            .file_name()
            .context("the run directory must name a new directory")?
            .to_string_lossy();
        if !cfg!(target_os = "linux") {
            return Ok(run_dir.join(POOL_SUBDIRECTORY));
        }
        let mut hasher = DefaultHasher::new();
        run_dir.hash(&mut hasher);
        let hash = hasher.finish() & 0xffff_ffff;
        Ok(PathBuf::from("/dev/shm").join(format!("cosim-{name}-{hash:08x}")))
    }

    /// Rejects identifiers whose session paths would collide.
    ///
    /// Metadata files contain a dot, which identifiers cannot, so only the
    /// pool subdirectory and vHost paths are reserved.
    pub fn check_identifiers(topology: &Topology) -> Result<()> {
        for machine in &topology.machines {
            ensure!(
                !machine.id.as_str().eq_ignore_ascii_case(POOL_SUBDIRECTORY),
                "machine identifier {} is reserved by the session layout",
                machine.id
            );
            for device in &machine.devices {
                ensure!(
                    !matches!(
                        device.id.as_str().to_ascii_lowercase().as_str(),
                        "vhost" | "qmp" | "serial"
                    ),
                    "device identifier {} in {} is reserved by the session layout",
                    device.id,
                    machine.id
                );
            }
        }
        Ok(())
    }

    /// Advisory lock held while the launcher or any session process runs.
    pub fn lock(&self) -> PathBuf {
        self.run_dir.join("session.lock")
    }

    /// Unpublished run metadata, beside the final run directory.
    pub(crate) fn run_staging(&self, token: &str) -> PathBuf {
        let name = self
            .run_dir
            .file_name()
            .map(|name| name.to_string_lossy())
            .unwrap_or_default();
        self.run_dir
            .with_file_name(format!(".{name}.{token}{RUN_STAGING_SUFFIX}"))
    }

    /// Resources that `cosim clean` may remove after the launcher stops.
    pub fn manifest(&self) -> PathBuf {
        self.run_dir.join("manifest.json")
    }

    /// The plan the session executes.
    pub fn plan(&self) -> PathBuf {
        self.run_dir.join("plan.json")
    }

    /// Run options of the session.
    pub fn options(&self) -> PathBuf {
        self.run_dir.join("options.json")
    }

    /// Final session result.
    pub fn verdict(&self) -> PathBuf {
        self.run_dir.join("verdict.json")
    }

    /// Ownership marker inside the pool directory.
    pub fn pool_marker(&self) -> PathBuf {
        Self::marker_in(&self.pool_dir)
    }

    /// Name beside the pool directory under which session `token` prepares
    /// the directory before publishing it, and moves it before removing it.
    pub(crate) fn pool_staging(&self, token: &str) -> PathBuf {
        let name = self
            .pool_dir
            .file_name()
            .map(|name| name.to_string_lossy())
            .unwrap_or_default();
        self.pool_dir
            .with_file_name(format!(".{name}.{token}{POOL_STAGING_SUFFIX}"))
    }

    /// Ownership marker inside a pool directory at `directory`.
    pub(crate) fn marker_in(directory: &Path) -> PathBuf {
        directory.join(POOL_MARKER)
    }

    /// Directory of one machine.
    pub fn machine_dir(&self, machine: &Identifier) -> PathBuf {
        self.run_dir.join(machine.as_str())
    }

    /// Recorded memory layout of one machine.
    pub fn memory_record(&self, machine: &Identifier) -> PathBuf {
        self.machine_dir(machine).join("layout.json")
    }

    /// Working directory of the vHost process.
    pub fn vhost_dir(&self, machine: &Identifier) -> PathBuf {
        self.machine_dir(machine).join("vhost")
    }

    /// Working directory of a device process.
    pub fn device_dir(&self, machine: &Identifier, device: &Identifier) -> PathBuf {
        self.machine_dir(machine).join(device.as_str())
    }

    /// Combined output log of a process.
    pub fn output_log(node_dir: &Path) -> PathBuf {
        node_dir.join(OUTPUT_LOG)
    }

    /// Temporary name under which a missing disk image is formatted.
    pub(crate) fn temporary_image(source: &Path, token: &str) -> Result<PathBuf> {
        let parent = source
            .parent()
            .context("the disk has no parent directory")?;
        let name = source
            .file_name()
            .context("the disk has no file name")?
            .to_string_lossy();
        Ok(parent.join(format!(".{name}.{token}{TEMPORARY_SUFFIX}")))
    }

    /// Returns whether `path` is a temporary image name of session `token`.
    pub(crate) fn is_temporary_image(path: &Path, token: &str) -> bool {
        path.file_name()
            .and_then(|name| name.to_str())
            .is_some_and(|name| {
                name.starts_with('.') && name.ends_with(&format!(".{token}{TEMPORARY_SUFFIX}"))
            })
    }

    /// Serial console log written by the vHost.
    pub fn serial_log(&self, machine: &Identifier) -> PathBuf {
        self.vhost_dir(machine).join("serial.log")
    }

    /// vfio-user socket of a device.
    pub fn device_socket(&self, machine: &Identifier, device: &Identifier) -> PathBuf {
        self.machine_dir(machine).join(format!("{device}.sock"))
    }

    /// QMP socket of a device.
    pub fn device_qmp(&self, machine: &Identifier, device: &Identifier) -> PathBuf {
        self.machine_dir(machine).join(format!("{device}.qmp.sock"))
    }

    /// QMP socket of the vHost.
    pub fn vhost_qmp(&self, machine: &Identifier) -> PathBuf {
        self.machine_dir(machine).join("qmp.sock")
    }

    /// Serial console socket of the vHost.
    pub fn vhost_serial(&self, machine: &Identifier) -> PathBuf {
        self.machine_dir(machine).join("serial.sock")
    }

    /// Memory pool file of a machine.
    pub fn pool(&self, machine: &Identifier) -> PathBuf {
        self.pool_dir.join(machine.as_str()).join("pool")
    }

    /// Session overlay of a disk.
    pub fn overlay(&self, machine: &Identifier, disk: &Identifier) -> PathBuf {
        self.machine_dir(machine).join(format!("{disk}.qcow2"))
    }

    /// Log of `qemu-img` invocations for a disk.
    pub fn disk_log(&self, machine: &Identifier, disk: &Identifier) -> PathBuf {
        self.machine_dir(machine)
            .join(format!("{disk}.qemu-img.log"))
    }
}

/// Makes `path` absolute and resolves symbolic links and `..` in its existing
/// part; the missing remainder may contain only plain names.
pub(crate) fn resolve(path: &Path) -> Result<PathBuf> {
    let path = std::path::absolute(path)?;
    let mut existing = path.as_path();
    while !existing
        .try_exists()
        .with_context(|| format!("inspect {}", existing.display()))?
    {
        existing = existing
            .parent()
            .with_context(|| format!("no part of {} exists", path.display()))?;
    }
    let missing = path.strip_prefix(existing)?;
    ensure!(
        missing
            .components()
            .all(|component| matches!(component, Component::Normal(_))),
        "{} continues after a missing directory with `..`",
        path.display()
    );
    let existing =
        fs::canonicalize(existing).with_context(|| format!("resolve {}", existing.display()))?;
    Ok(existing.join(missing))
}

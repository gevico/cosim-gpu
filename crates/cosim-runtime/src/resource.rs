// SPDX-License-Identifier: Apache-2.0

//! Owners of the files, directories and locks of a session.
//!
//! Files and directories that session processes use are removed only by an
//! explicit `remove` after their users have stopped. Dropping such an owner
//! leaves the path in place for `cosim clean`, because termination of the
//! users is not confirmed on that path.
//!
//! Lock descriptors are close-on-exec; a session passes them explicitly to
//! the processes it starts.

use std::fs::{self, DirBuilder, File, Metadata, OpenOptions, TryLockError};
use std::io::ErrorKind;
use std::os::fd::{AsFd, BorrowedFd};
use std::os::unix::fs::{DirBuilderExt, FileTypeExt, MetadataExt, OpenOptionsExt};
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, anyhow, ensure};

/// A file owned by the session.
#[must_use = "an owned file must be removed after its users stop"]
pub(crate) struct OwnedFile {
    path: PathBuf,
}

impl OwnedFile {
    /// Creates a new file with mode 0600 and fails if the path exists.
    pub(crate) fn create(path: &Path) -> Result<(Self, File)> {
        let file = new_file(path)?;
        Ok((Self::adopt(path.to_path_buf()), file))
    }

    /// Takes ownership of a path that exists or that a helper will create.
    pub(crate) fn adopt(path: PathBuf) -> Self {
        Self { path }
    }

    /// Removes the file; a missing file counts as removed.
    pub(crate) fn remove(self) -> Result<()> {
        remove_file(&self.path)
    }
}

/// A Unix socket created by an owned process.
#[must_use = "an endpoint must be removed after its process stops"]
pub(crate) struct Endpoint {
    path: PathBuf,
}

impl Endpoint {
    pub(crate) fn adopt(path: PathBuf) -> Self {
        Self { path }
    }

    /// Removes the socket and rejects other file types at its path.
    pub(crate) fn remove(self) -> Result<()> {
        match fs::symlink_metadata(&self.path) {
            Ok(metadata) => {
                ensure!(
                    metadata.file_type().is_socket(),
                    "expected a socket at {}",
                    self.path.display()
                );
                remove_file(&self.path)
            }
            Err(error) if error.kind() == ErrorKind::NotFound => Ok(()),
            Err(error) => Err(error).with_context(|| format!("inspect {}", self.path.display())),
        }
    }
}

/// A directory owned by the session.
#[must_use = "an owned directory must be removed after its users stop"]
pub(crate) struct OwnedDir {
    path: PathBuf,
}

impl OwnedDir {
    /// Creates a new directory with mode 0700 and fails if the path exists.
    pub(crate) fn create(path: &Path) -> Result<Self> {
        new_dir(path)?;
        Ok(Self::adopt(path.to_path_buf()))
    }

    pub(crate) fn adopt(path: PathBuf) -> Self {
        Self { path }
    }

    /// Removes the directory, which must be empty.
    pub(crate) fn remove(self) -> Result<()> {
        match fs::remove_dir(&self.path) {
            Ok(()) => Ok(()),
            Err(error) if error.kind() == ErrorKind::NotFound => Ok(()),
            Err(error) => Err(error).with_context(|| format!("remove {}", self.path.display())),
        }
    }
}

/// A directory created during session initialization.
///
/// No process uses it yet, so dropping the value removes it with its contents
/// unless initialization completes.
pub(crate) struct NewDir {
    path: PathBuf,
    keep: bool,
}

impl NewDir {
    /// Creates the parents and a new directory with mode 0700.
    pub(crate) fn create(path: &Path) -> Result<Self> {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).with_context(|| format!("create {}", parent.display()))?;
        }
        new_dir(path)?;
        Ok(Self {
            path: path.to_path_buf(),
            keep: false,
        })
    }

    /// Path of the directory.
    pub(crate) fn path(&self) -> &Path {
        &self.path
    }

    /// Moves the directory with its contents to `target`, which must not
    /// exist, in one step.
    ///
    /// Other processes observe either no directory at `target` or the
    /// complete one.
    pub(crate) fn publish(mut self, target: &Path) -> Result<Self> {
        rename_new(&self.path, target)?;
        self.path = target.to_path_buf();
        Ok(self)
    }

    /// Keeps the directory after initialization succeeded.
    pub(crate) fn commit(mut self) {
        self.keep = true;
    }
}

impl Drop for NewDir {
    fn drop(&mut self) {
        if !self.keep {
            let _ = fs::remove_dir_all(&self.path);
        }
    }
}

/// Renames `source` to `target` and fails if `target` exists.
#[cfg(all(target_os = "linux", target_env = "gnu"))]
fn rename_new(source: &Path, target: &Path) -> Result<()> {
    use nix::fcntl::{self, AT_FDCWD, RenameFlags};

    fcntl::renameat2(
        AT_FDCWD,
        source,
        AT_FDCWD,
        target,
        RenameFlags::RENAME_NOREPLACE,
    )
    .with_context(|| format!("publish {} as {}", source.display(), target.display()))
}

/// Renames `source` to `target` and fails if `target` exists.
#[cfg(not(all(target_os = "linux", target_env = "gnu")))]
fn rename_new(source: &Path, target: &Path) -> Result<()> {
    anyhow::bail!(
        "publishing {} as {} requires Linux with glibc",
        source.display(),
        target.display()
    )
}

/// Creates a new directory with mode 0700, limited by the umask, in one step.
fn new_dir(path: &Path) -> Result<()> {
    DirBuilder::new()
        .mode(0o700)
        .create(path)
        .with_context(|| format!("create new directory {}", path.display()))
}

/// Creates a new file with mode 0600 and fails if the path exists.
pub(crate) fn new_file(path: &Path) -> Result<File> {
    OpenOptions::new()
        .read(true)
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(path)
        .with_context(|| format!("create {}", path.display()))
}

/// Reserves storage before a process can map and write a memory pool.
#[cfg(target_os = "linux")]
pub(crate) fn reserve(file: &File, size: u64) -> Result<()> {
    let length = size
        .try_into()
        .context("memory pool exceeds the file size limit")?;
    nix::fcntl::posix_fallocate(file, 0, length).context("allocate memory pool storage")
}

/// Memory pool reservations require the supported Linux execution host.
#[cfg(not(target_os = "linux"))]
pub(crate) fn reserve(_file: &File, _size: u64) -> Result<()> {
    anyhow::bail!("memory pool reservations require Linux")
}

/// The advisory lock that marks a session as running.
///
/// Every session process receives the lock descriptor, so the lock stays held
/// while the launcher or any session process, including forked workers, is
/// alive. The lock works across PID namespaces of one kernel.
pub(crate) struct RunLock {
    file: File,
}

impl RunLock {
    /// Creates and locks a new lock file.
    pub(crate) fn create(path: &Path) -> Result<Self> {
        Self::lock(new_file(path)?, path)
    }

    /// Locks the lock file of a session whose processes have all exited.
    pub(crate) fn acquire(path: &Path) -> Result<Self> {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .open(path)
            .with_context(|| format!("open {}", path.display()))?;
        Self::lock(file, path)
    }

    fn lock(file: File, path: &Path) -> Result<Self> {
        file.try_lock().map_err(|error| match error {
            TryLockError::WouldBlock => {
                anyhow!("the launcher or one of its processes is still running")
            }
            TryLockError::Error(error) => {
                anyhow!(error).context(format!("lock {}", path.display()))
            }
        })?;
        Ok(Self { file })
    }
}

impl AsFd for RunLock {
    fn as_fd(&self) -> BorrowedFd<'_> {
        self.file.as_fd()
    }
}

/// Device and inode numbers that identify a file across links.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct FileId {
    device: u64,
    inode: u64,
}

impl FileId {
    pub(crate) fn of(path: &Path) -> Result<Self> {
        let metadata = fs::metadata(path).with_context(|| format!("inspect {}", path.display()))?;
        Ok(Self::from(&metadata))
    }
}

impl From<&Metadata> for FileId {
    fn from(metadata: &Metadata) -> Self {
        Self {
            device: metadata.dev(),
            inode: metadata.ino(),
        }
    }
}

/// Access requested from cooperating sessions for one image.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum LeaseKind {
    /// Readers and overlay backings.
    Shared,
    /// A direct writer.
    Exclusive,
}

/// An image lock keyed by device and inode in the shared lock directory.
///
/// The vHost and the helpers that use the image receive the lock descriptor,
/// so the lease lasts while any process that may use the image is alive. Lock
/// files remain after release so that every session locks the same file.
pub(crate) struct DiskLease {
    file: File,
}

impl DiskLease {
    pub(crate) fn acquire(directory: &Path, image: FileId, kind: LeaseKind) -> Result<Self> {
        fs::create_dir_all(directory).with_context(|| format!("create {}", directory.display()))?;
        let path = directory.join(format!("{}-{}", image.device, image.inode));
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .mode(0o600)
            .open(&path)
            .with_context(|| format!("open {}", path.display()))?;
        let result = match kind {
            LeaseKind::Shared => file.try_lock_shared(),
            LeaseKind::Exclusive => file.try_lock(),
        };
        result.map_err(|error| match error {
            TryLockError::WouldBlock => anyhow!("the image is in use by another session"),
            TryLockError::Error(error) => {
                anyhow!(error).context(format!("lock {}", path.display()))
            }
        })?;
        Ok(Self { file })
    }
}

impl AsFd for DiskLease {
    fn as_fd(&self) -> BorrowedFd<'_> {
        self.file.as_fd()
    }
}

fn remove_file(path: &Path) -> Result<()> {
    match fs::remove_file(path) {
        Ok(()) => Ok(()),
        Err(error) if error.kind() == ErrorKind::NotFound => Ok(()),
        Err(error) => Err(error).with_context(|| format!("remove {}", path.display())),
    }
}

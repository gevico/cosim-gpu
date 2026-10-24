// SPDX-License-Identifier: Apache-2.0

//! Validated topology values consumed by planners and tools.

use std::collections::BTreeMap;
use std::fmt;
use std::num::NonZeroU32;
use std::path::PathBuf;
use std::time::Duration;

use anyhow::{Result, ensure};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

use crate::adapter::{Adapter, CommandTemplate};
use crate::size::ByteSize;

/// A topology whose references, identifiers and resource declarations are valid.
///
/// Construct it with [`crate::load`]. All values are independent of the
/// system that will execute the topology.
#[non_exhaustive]
#[derive(Clone, Debug, Serialize)]
pub struct Topology {
    /// Canonical path of the loaded document.
    pub source: PathBuf,
    /// Expanded machine instances in declaration order.
    pub machines: Vec<Machine>,
}

impl Topology {
    /// Returns the number of expanded device instances.
    pub fn device_count(&self) -> usize {
        self.machines
            .iter()
            .map(|machine| machine.devices.len())
            .sum()
    }
}

/// A name of 1 to 48 ASCII letters, digits, underscores or hyphens.
#[derive(Clone, Debug, Eq, Hash, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(transparent)]
pub struct Identifier(String);

impl Identifier {
    pub(crate) fn new(value: impl Into<String>) -> Result<Self> {
        let value = value.into();
        ensure!(
            !value.is_empty()
                && value.len() <= 48
                && value
                    .bytes()
                    .all(|byte| byte.is_ascii_alphanumeric() || byte == b'-' || byte == b'_'),
            "invalid identifier {value:?}; use 1..48 letters, digits, underscores or hyphens"
        );
        Ok(Self(value))
    }

    /// Returns the identifier text.
    pub fn as_str(&self) -> &str {
        &self.0
    }

    /// Returns the identifier without ASCII case distinctions.
    pub(crate) fn folded(&self) -> String {
        self.0.to_ascii_lowercase()
    }
}

impl fmt::Display for Identifier {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(&self.0)
    }
}

/// One QEMU vHost and the device processes connected to it.
#[non_exhaustive]
#[derive(Clone, Debug, Serialize)]
pub struct Machine {
    /// Machine identifier after count expansion.
    pub id: Identifier,
    /// The QEMU vHost process.
    pub vhost: Vhost,
    /// Device processes in declaration order.
    pub devices: Vec<Device>,
    /// Remote agent reserved for distributed execution.
    pub placement: Option<String>,
}

/// Image selection resolved as part of one vHost.
#[non_exhaustive]
#[derive(Clone, Debug, Serialize)]
pub struct ImageRecipe {
    /// Recipe identifier relative to `resources/images/recipes`.
    pub recipe: String,
    /// Bus used to attach the recipe's root disk.
    pub root_bus: DiskBus,
    /// Command line used with the recipe's matching kernel.
    pub cmdline: Option<String>,
}

/// An executable and the environment it receives.
#[non_exhaustive]
#[derive(Clone, Debug, Serialize)]
pub struct Program {
    /// Absolute path, or a command name searched in `PATH`.
    pub binary: String,
    /// Explicit environment variables; other variables are not inherited.
    pub env: BTreeMap<String, String>,
}

/// QEMU vHost configuration.
#[non_exhaustive]
#[derive(Clone, Debug, Serialize)]
pub struct Vhost {
    /// Name of the vHost adapter kind.
    pub kind: String,
    /// Command template that renders the QEMU arguments.
    pub command: CommandTemplate,
    /// QEMU executable and environment.
    pub program: Program,
    /// Guest RAM size.
    pub memory: ByteSize,
    /// Alignment of guest RAM inside the memory pool.
    pub memory_align: ByteSize,
    /// MiniJinja template rendering guest physical RAM ranges.
    pub memory_map: Option<String>,
    /// Number of virtual CPUs.
    pub cpus: NonZeroU32,
    /// QEMU accelerator.
    pub accel: String,
    /// QEMU machine type and properties.
    pub machine: String,
    /// QEMU CPU model.
    pub cpu: Option<String>,
    /// QEMU display backend.
    pub display: Option<String>,
    /// QEMU monitor backend.
    pub monitor: Option<String>,
    /// Exit instead of rebooting the guest.
    pub no_reboot: bool,
    /// Guest serial output that marks the vHost ready.
    pub serial_ready: Option<SerialReady>,
    /// Additional QEMU arguments.
    pub args: Vec<String>,
    /// Image recipe awaiting runtime resolution.
    pub image: Option<ImageRecipe>,
    /// Direct kernel boot configuration after image resolution.
    pub boot: Option<DirectBoot>,
    /// Storage attached to this vHost.
    pub disks: Vec<Disk>,
}

/// Kernel, initial RAM disk and command line for direct boot.
#[non_exhaustive]
#[derive(Clone, Debug, Serialize)]
pub struct DirectBoot {
    /// Kernel image.
    pub kernel: PathBuf,
    /// Initial RAM disk.
    pub initrd: Option<PathBuf>,
    /// Kernel command line.
    pub cmdline: Option<String>,
}

/// A serial marker that completes vHost readiness.
#[non_exhaustive]
#[derive(Clone, Debug, Serialize)]
pub struct SerialReady {
    /// Text the guest prints on its serial console.
    pub marker: String,
    /// Deadline measured from vHost start; the run's readiness timeout applies otherwise.
    pub timeout: Option<Duration>,
}

/// A disk image attached to the vHost.
#[non_exhaustive]
#[derive(Clone, Debug, Serialize)]
pub struct Disk {
    /// Disk identifier, unique within its vHost.
    pub id: Identifier,
    /// Image that the disk reads or writes.
    pub source: PathBuf,
    /// Format of the source image.
    pub format: DiskFormat,
    /// Guest bus.
    pub bus: DiskBus,
    /// Whether the guest boots from this disk.
    pub boot: bool,
    /// How the vHost opens the source image.
    pub mode: DiskMode,
    /// Size of a source image created when it is missing.
    pub create: Option<ByteSize>,
}

/// Image formats supported for disk sources.
#[derive(
    Clone, Copy, Debug, Default, Deserialize, Eq, JsonSchema, Ord, PartialEq, PartialOrd, Serialize,
)]
#[serde(rename_all = "lowercase")]
pub enum DiskFormat {
    /// Raw image.
    Raw,
    /// QEMU copy-on-write image.
    #[default]
    Qcow2,
}

impl DiskFormat {
    /// Returns the QEMU format name.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Raw => "raw",
            Self::Qcow2 => "qcow2",
        }
    }
}

/// Guest buses for attached disks.
#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, JsonSchema, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum DiskBus {
    /// virtio-blk PCI device.
    #[default]
    Virtio,
    /// NVMe controller.
    Nvme,
    /// IDE disk.
    Ide,
    /// SCSI disk on a virtio-scsi controller.
    Scsi,
}

/// Access to a disk source.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum DiskMode {
    /// The vHost opens the source read-only.
    ReadOnly,
    /// The vHost writes a per-machine overlay backed by the source.
    Overlay,
    /// The vHost writes the source directly.
    Direct,
}

/// Simulators that implement device models.
#[derive(Clone, Copy, Debug, Deserialize, Eq, JsonSchema, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum DeviceModel {
    /// gem5.
    Gem5,
    /// QEMU.
    Qemu,
}

/// Roles that an adapter kind can fill.
#[derive(Clone, Copy, Debug, Deserialize, Eq, JsonSchema, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    /// A device process connected through vfio-user.
    Device,
    /// The QEMU vHost process.
    Vhost,
}

/// A device process.
#[non_exhaustive]
#[derive(Clone, Debug, Serialize)]
pub struct Device {
    /// Device identifier after count expansion.
    pub id: Identifier,
    /// Name of the device kind.
    pub kind: String,
    /// Simulator that implements the device.
    pub model: DeviceModel,
    /// Launch contract.
    pub adapter: Adapter,
    /// Executable and environment.
    pub program: Program,
    /// Device-private regions in the machine memory pool.
    pub regions: Vec<MemoryRegion>,
    /// PCI identity reported by the model.
    pub pci: Pci,
    /// Guest configuration suggested by the device.
    pub guest_hints: GuestHints,
}

/// A device-private region in the machine memory pool.
#[non_exhaustive]
#[derive(Clone, Debug, Serialize)]
pub struct MemoryRegion {
    /// Region name, unique within its device.
    pub name: Identifier,
    /// Region size.
    pub size: ByteSize,
    /// Region alignment, a power of two.
    pub align: ByteSize,
}

/// PCI identity and vHost-side option ROM.
#[derive(Clone, Debug, Default, Deserialize, JsonSchema, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Pci {
    /// PCI vendor identifier.
    pub vendor_id: Option<u16>,
    /// PCI device identifier.
    pub device_id: Option<u16>,
    /// Number of MSI-X vectors.
    pub msix_vectors: Option<u16>,
    /// Option ROM exposed by the vHost's vfio-user PCI device.
    pub rom: Option<PathBuf>,
}

/// Guest configuration suggested by a device.
#[derive(Clone, Debug, Default, Deserialize, JsonSchema, Serialize)]
#[serde(deny_unknown_fields)]
pub struct GuestHints {
    /// Driver load command recorded in the plan.
    pub modprobe: Option<String>,
    /// Kernel command-line text appended for direct boot.
    pub cmdline: Option<String>,
}

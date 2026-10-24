// SPDX-License-Identifier: Apache-2.0

//! Launch contracts that turn validated nodes into process arguments.

mod gem5;
mod qemu_device;
mod template;

use std::path::{Path, PathBuf};
use std::time::Duration;

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

pub use gem5::Gem5Mi300x;
pub use qemu_device::QemuDevice;
pub use template::{CommandTemplate, TemplateDevice};

use crate::layout::MemoryLayout;
use crate::model::{Device, DirectBoot, Disk, DiskFormat, Machine, Vhost};

/// The launch contract of a device process.
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "kebab-case", tag = "adapter")]
pub enum Adapter {
    /// One MI300X GPU in gem5.
    Gem5Mi300x(Gem5Mi300x),
    /// A QEMU device model exported through `x-vfio-user-server`.
    QemuDevice(QemuDevice),
    /// A command rendered from a YAML template.
    Template(TemplateDevice),
}

/// A readiness condition, checked in order after a process starts.
#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "kebab-case", tag = "probe")]
pub enum Probe {
    /// An append-only log contains a marker.
    Log {
        /// Log file.
        path: PathBuf,
        /// Text to find.
        marker: String,
        /// Deadline from process start; the run's readiness timeout applies otherwise.
        timeout: Option<Duration>,
    },
    /// A Unix socket exists.
    Socket {
        /// Socket path.
        path: PathBuf,
    },
    /// A QMP server completes capability negotiation.
    Qmp {
        /// QMP socket path.
        path: PathBuf,
    },
}

/// Arguments and readiness conditions of one process.
#[non_exhaustive]
#[derive(Clone, Debug)]
pub struct Launch {
    /// Process arguments, excluding the executable.
    pub argv: Vec<String>,
    /// Readiness conditions in evaluation order.
    pub probes: Vec<Probe>,
}

/// Session paths assigned to a device process.
#[derive(Clone, Copy, Debug)]
pub struct DeviceContext<'a> {
    /// Owning machine.
    pub machine: &'a Machine,
    /// Memory layout of the machine pool.
    pub layout: &'a MemoryLayout,
    /// Machine memory pool file.
    pub pool: &'a Path,
    /// vfio-user socket.
    pub socket: &'a Path,
    /// QMP socket for adapters that expose one.
    pub qmp: &'a Path,
    /// Combined standard output and error log.
    pub output_log: &'a Path,
    /// Working directory of the process.
    pub node_dir: &'a Path,
    /// Session directory.
    pub run_dir: &'a Path,
}

/// A disk as the vHost process opens it.
#[derive(Clone, Copy, Debug)]
pub struct VhostDisk<'a> {
    /// Disk declaration.
    pub disk: &'a Disk,
    /// File passed to QEMU: the source or a session overlay.
    pub path: &'a Path,
    /// Format of `path`.
    pub format: DiskFormat,
    /// Whether QEMU opens `path` read-only.
    pub readonly: bool,
}

/// A device endpoint the vHost connects to.
#[derive(Clone, Copy, Debug)]
pub struct VhostDevice<'a> {
    /// Device declaration.
    pub device: &'a Device,
    /// vfio-user socket served by the device.
    pub socket: &'a Path,
}

/// Session paths assigned to the vHost process.
#[derive(Clone, Debug)]
pub struct VhostContext<'a> {
    /// Owning machine.
    pub machine: &'a Machine,
    /// Memory layout of the machine pool.
    pub layout: &'a MemoryLayout,
    /// Machine memory pool file.
    pub pool: &'a Path,
    /// QMP socket.
    pub qmp: &'a Path,
    /// Serial console socket.
    pub serial: &'a Path,
    /// Serial console log written by QEMU.
    pub serial_log: &'a Path,
    /// Working directory of the process.
    pub node_dir: &'a Path,
    /// Session directory.
    pub run_dir: &'a Path,
    /// Optional direct-boot configuration owned by the vHost.
    pub boot: Option<&'a DirectBoot>,
    /// Disks in declaration order.
    pub disks: Vec<VhostDisk<'a>>,
    /// Device endpoints in declaration order.
    pub devices: Vec<VhostDevice<'a>>,
}

impl Device {
    /// Renders the device arguments and readiness conditions.
    pub fn launch(&self, context: &DeviceContext<'_>) -> Result<Launch> {
        match &self.adapter {
            Adapter::Gem5Mi300x(adapter) => adapter.launch(self, context),
            Adapter::QemuDevice(adapter) => adapter.launch(context),
            Adapter::Template(adapter) => adapter.launch(self, context),
        }
        .with_context(|| format!("device {} adapter {}", self.id, self.kind))
    }
}

impl Vhost {
    /// Renders the vHost arguments and readiness conditions.
    pub fn launch(&self, context: &VhostContext<'_>) -> Result<Launch> {
        let disks = context
            .disks
            .iter()
            .map(|disk| {
                json!({"id": disk.disk.id, "path": disk.path, "format": disk.format,
                    "readonly": disk.readonly, "bus": disk.disk.bus, "boot": disk.disk.boot})
            })
            .collect::<Vec<_>>();
        let devices = context
            .devices
            .iter()
            .map(|device| {
                json!({"id": device.device.id, "socket": device.socket,
                    "model": device.device.model, "pci": device.device.pci})
            })
            .collect::<Vec<_>>();
        let template_context = json!({"vhost": self, "machine": context.machine.id,
            "pool": context.pool, "ram": context.layout.ram,
            "guest_ranges": context.layout.guest_ranges, "disks": disks,
            "devices": devices, "qmp": context.qmp, "serial": context.serial,
            "serial_log": context.serial_log, "boot": context.boot,
            "cmdline": self.cmdline(context.machine, context.boot),
            "run_dir": context.run_dir, "node_dir": context.node_dir});
        let argv = self
            .command
            .render(&template_context)
            .with_context(|| format!("vhost adapter {}", self.kind))?;
        let mut probes = vec![
            Probe::Socket {
                path: context.serial.to_path_buf(),
            },
            Probe::Qmp {
                path: context.qmp.to_path_buf(),
            },
        ];
        if let Some(ready) = &self.serial_ready {
            probes.push(Probe::Log {
                path: context.serial_log.to_path_buf(),
                marker: ready.marker.clone(),
                timeout: ready.timeout,
            });
        }
        Ok(Launch { argv, probes })
    }

    /// Joins the boot command line with device guest hints.
    fn cmdline(&self, machine: &Machine, boot: Option<&DirectBoot>) -> Value {
        let Some(boot) = boot else {
            return Value::String(String::new());
        };
        let parts = boot
            .cmdline
            .iter()
            .chain(
                machine
                    .devices
                    .iter()
                    .filter_map(|device| device.guest_hints.cmdline.as_ref()),
            )
            .map(String::as_str)
            .collect::<Vec<_>>();
        Value::String(parts.join(" "))
    }
}

/// Returns QEMU socket option text with commas escaped.
fn qemu_path(path: &Path) -> String {
    path.to_string_lossy().replace(',', ",,")
}

// SPDX-License-Identifier: Apache-2.0

//! Checks for local input files referenced by a topology.

use std::fs;
use std::io::ErrorKind;
use std::path::Path;

use anyhow::{Context, Result, ensure};
use cosim_topology::{Adapter, Topology};

/// Checks boot images, disks, device configuration and PCI option ROMs.
pub fn check_assets(topology: &Topology) -> Result<()> {
    for machine in &topology.machines {
        let check = || -> Result<()> {
            if let Some(boot) = &machine.vhost.boot {
                for path in std::iter::once(&boot.kernel).chain(&boot.initrd) {
                    file(path, "boot image")?;
                }
            }
            for disk in &machine.vhost.disks {
                match fs::symlink_metadata(&disk.source) {
                    Ok(_) => file(&disk.source, "disk source")?,
                    Err(error) if error.kind() == ErrorKind::NotFound => {
                        ensure!(
                            disk.create.is_some(),
                            "missing disk {}",
                            disk.source.display()
                        );
                        let parent = disk.source.parent().context("disk has no parent")?;
                        ensure!(
                            parent.is_dir(),
                            "missing disk directory {}",
                            parent.display()
                        );
                    }
                    Err(error) => {
                        return Err(error)
                            .with_context(|| format!("inspect {}", disk.source.display()));
                    }
                }
            }
            for device in &machine.devices {
                if let Some(rom) = &device.pci.rom {
                    file(rom, "PCI option ROM")?;
                }
                let config = match &device.adapter {
                    Adapter::Gem5Mi300x(adapter) => Some(adapter.config.as_path()),
                    Adapter::Template(adapter) => adapter.config.as_deref(),
                    Adapter::QemuDevice(_) => None,
                };
                if let Some(config) = config {
                    file(config, "device configuration")?;
                }
            }
            Ok(())
        };
        check().with_context(|| format!("machine {}", machine.id))?;
    }
    Ok(())
}

fn file(path: &Path, what: &str) -> Result<()> {
    ensure!(path.is_file(), "missing {what} {}", path.display());
    fs::File::open(path).with_context(|| format!("read {what} {}", path.display()))?;
    Ok(())
}

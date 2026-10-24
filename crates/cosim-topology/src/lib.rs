// SPDX-License-Identifier: Apache-2.0

//! Loads YAML topology descriptions into validated values.
//!
//! The crate reads only topology documents. Values that depend on the
//! executing system, such as page size, `PATH` and session paths, are
//! supplied by callers through [`PageSize`], [`DeviceContext`] and
//! [`VhostContext`].

mod adapter;
mod graph;
mod layout;
mod loader;
mod model;
mod raw;
mod resolve;
mod size;

pub use adapter::{
    Adapter, CommandTemplate, DeviceContext, Gem5Mi300x, Launch, Probe, QemuDevice, TemplateDevice,
    VhostContext, VhostDevice, VhostDisk,
};
pub use graph::graph;
pub use layout::{DeviceRegions, GuestRange, MemoryLayout, PageSize, Region};
pub use loader::{load, load_with_workspace};
pub use model::{
    Device, DeviceModel, DirectBoot, Disk, DiskBus, DiskFormat, DiskMode, GuestHints, Identifier,
    ImageRecipe, Machine, MemoryRegion, Pci, Program, Role, SerialReady, Topology, Vhost,
};
pub use size::ByteSize;

/// Adds the verified kernel and root disk selected by one vHost image recipe.
pub fn materialize_image_recipe(
    vhost: &mut Vhost,
    kernel: Option<std::path::PathBuf>,
    disk: std::path::PathBuf,
    disk_format: DiskFormat,
) -> anyhow::Result<()> {
    resolve::materialize_image_recipe(vhost, kernel, disk, disk_format)
}

/// Generates the JSON Schema of topology documents.
pub fn schema() -> schemars::Schema {
    schemars::schema_for!(raw::Document)
}

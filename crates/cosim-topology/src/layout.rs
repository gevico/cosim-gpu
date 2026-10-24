// SPDX-License-Identifier: Apache-2.0

//! Shared-memory layout of a machine for a given execution page size.

use std::fmt;

use anyhow::{Context, Result, ensure};
use minijinja::{Environment, UndefinedBehavior};
use serde::{Deserialize, Serialize};
use serde_json::json;

use crate::model::{Identifier, Machine, Vhost};
use crate::size::ByteSize;

/// Memory page size of the system that maps the pool.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(transparent)]
pub struct PageSize(u64);

impl PageSize {
    /// Accepts powers of two of at least 4 KiB.
    pub fn new(bytes: u64) -> Result<Self> {
        ensure!(
            bytes >= 4096 && bytes.is_power_of_two(),
            "unsupported page size {bytes}"
        );
        Ok(Self(bytes))
    }

    /// Returns the page size in bytes.
    pub fn bytes(self) -> u64 {
        self.0
    }
}

impl fmt::Display for PageSize {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{}", self.0)
    }
}

/// A byte range inside the machine memory pool.
#[non_exhaustive]
#[derive(Clone, Debug, Serialize)]
pub struct Region {
    /// Region name.
    pub name: String,
    /// Byte offset in the pool file.
    pub offset: u64,
    /// Region size in bytes.
    pub size: u64,
    /// Region alignment in bytes.
    pub align: u64,
}

/// The private regions of one device.
#[non_exhaustive]
#[derive(Clone, Debug, Serialize)]
pub struct DeviceRegions {
    /// Owning device.
    pub device: Identifier,
    /// Regions in declaration order.
    pub regions: Vec<Region>,
}

/// A guest physical RAM range and its offset in the guest RAM region.
#[non_exhaustive]
#[derive(Clone, Debug, Serialize)]
pub struct GuestRange {
    /// Guest physical start address.
    pub start: u64,
    /// Range size in bytes.
    pub size: u64,
    /// Offset from the start of guest RAM.
    pub offset: u64,
}

/// The layout of one machine memory pool.
#[non_exhaustive]
#[derive(Clone, Debug, Serialize)]
pub struct MemoryLayout {
    /// Pool file size in bytes.
    pub size: u64,
    /// Guest RAM, the first region of the pool.
    pub ram: Region,
    /// Device-private regions following guest RAM.
    pub devices: Vec<DeviceRegions>,
    /// Guest physical RAM ranges; empty without `vhost.memory_map`.
    pub guest_ranges: Vec<GuestRange>,
}

impl MemoryLayout {
    /// Returns the private regions of a device.
    pub fn regions_of(&self, device: &Identifier) -> &[Region] {
        self.devices
            .iter()
            .find(|regions| &regions.device == device)
            .map_or(&[], |regions| &regions.regions)
    }
}

impl Machine {
    /// Places guest RAM and device regions in one pool file.
    ///
    /// Sizes must be multiples of the page size and alignments must be at
    /// least one page.
    pub fn memory_layout(&self, page_size: PageSize) -> Result<MemoryLayout> {
        let mut pool = PoolBuilder { page_size, size: 0 };
        let ram = pool.region("guest_ram", self.vhost.memory, self.vhost.memory_align)?;
        let mut devices = Vec::with_capacity(self.devices.len());
        for device in &self.devices {
            let regions = device
                .regions
                .iter()
                .map(|region| pool.region(region.name.as_str(), region.size, region.align))
                .collect::<Result<Vec<_>>>()
                .with_context(|| format!("device {}", device.id))?;
            devices.push(DeviceRegions {
                device: device.id.clone(),
                regions,
            });
        }
        let guest_ranges = guest_ranges(&self.vhost, ram.size, page_size)?;
        Ok(MemoryLayout {
            size: pool.size,
            ram,
            devices,
            guest_ranges,
        })
    }
}

struct PoolBuilder {
    page_size: PageSize,
    size: u64,
}

impl PoolBuilder {
    fn region(&mut self, name: &str, size: ByteSize, align: ByteSize) -> Result<Region> {
        let page = self.page_size.bytes();
        let (size, align) = (size.bytes(), align.bytes());
        ensure!(
            size % page == 0,
            "region {name} size must be a multiple of the {page}-byte page size"
        );
        ensure!(
            align >= page && align.is_power_of_two(),
            "region {name} alignment must be a power of two of at least {page} bytes"
        );
        let offset = self
            .size
            .checked_add(align - 1)
            .context("memory pool alignment overflow")?
            & !(align - 1);
        self.size = offset
            .checked_add(size)
            .context("memory pool size overflow")?;
        ensure!(
            self.size <= i64::MAX as u64,
            "memory pool exceeds the maximum file size"
        );
        Ok(Region {
            name: name.to_owned(),
            offset,
            size,
            align,
        })
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct GuestRangeInput {
    start: u64,
    size: ByteSize,
}

fn guest_ranges(vhost: &Vhost, ram_size: u64, page_size: PageSize) -> Result<Vec<GuestRange>> {
    let Some(template) = &vhost.memory_map else {
        return Ok(Vec::new());
    };
    let mut environment = Environment::new();
    environment.set_undefined_behavior(UndefinedBehavior::Strict);
    let rendered = environment
        .render_str(template, json!({"vhost": vhost, "ram": {"size": ram_size}}))
        .context("render vhost.memory_map")?;
    let inputs: Vec<GuestRangeInput> = serde_json::from_str(&rendered)
        .context("vhost.memory_map must render a JSON array of start/size ranges")?;
    ensure!(
        !inputs.is_empty() && inputs.len() <= 64,
        "vhost.memory_map requires 1..64 ranges"
    );
    let page = page_size.bytes();
    let mut ranges = Vec::with_capacity(inputs.len());
    let mut offset = 0u64;
    let mut previous_end = 0u64;
    for input in inputs {
        let size = input.size.bytes();
        ensure!(
            input.start % page == 0 && size % page == 0,
            "guest memory ranges must be multiples of the {page}-byte page size"
        );
        ensure!(
            input.start >= previous_end,
            "guest memory ranges overlap or are unordered"
        );
        previous_end = input
            .start
            .checked_add(size)
            .context("guest address range overflow")?;
        ranges.push(GuestRange {
            start: input.start,
            size,
            offset,
        });
        offset = offset
            .checked_add(size)
            .context("guest memory size overflow")?;
    }
    ensure!(
        offset == ram_size,
        "vhost.memory_map ranges must cover exactly vhost.memory"
    );
    Ok(ranges)
}

// SPDX-License-Identifier: Apache-2.0

use std::fs;
use std::path::{Path, PathBuf};

use anyhow::Result;
use cosim_topology::{
    Adapter, DeviceContext, DiskFormat, DiskMode, Machine, PageSize, Probe, Topology, VhostContext,
    VhostDevice, VhostDisk, load_with_workspace,
};
use serde_json::json;

/// A vHost kind, a device kind and a vHost template shared by test documents.
const BASE: &str = r#"
version: 1
kinds:
  vhost:
    role: vhost
    model: qemu
    max_devices: 4
    argv: ["-m", "{{ ram.size }}"]
  model:
    role: device
    model: qemu
    command: '{{ [config, socket, regions.buffer.offset | string, args.mode] | tojson }}'
templates:
  base: {kind: vhost, runtime: {binary: qemu}, memory: 64M, cpus: 1, accel: tcg, machine: q35}
"#;

fn write(root: &Path, path: &str, text: &str) -> PathBuf {
    let path = root.join(path);
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(&path, text).unwrap();
    path
}

/// Writes `lib/base.yaml` and a top-level document that imports it.
fn document(root: &Path, body: &str) -> PathBuf {
    write(root, "lib/base.yaml", BASE);
    write(
        root,
        "topology.yaml",
        &format!("version: 1\nimports: [lib/base.yaml]\n{body}"),
    )
}

/// Loads a document whose single machine uses the base vHost.
fn machine(root: &Path, vhost: &str, devices: &str) -> Result<Topology> {
    let body =
        format!("machines:\n  - id: m\n    vhost: {{use: base{vhost}}}\n    devices: {devices}\n");
    load_with_workspace(&document(root, &body), root, root)
}

fn failure(result: Result<impl std::fmt::Debug>) -> String {
    format!("{:#}", result.expect_err("the input must be rejected"))
}

fn resources() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../resources")
}

fn page() -> PageSize {
    PageSize::new(4096).unwrap()
}

/// Returns a temporary directory and its canonical path.
fn tempdir() -> (tempfile::TempDir, PathBuf) {
    let directory = tempfile::tempdir().unwrap();
    let path = fs::canonicalize(directory.path()).unwrap();
    (directory, path)
}

#[test]
fn workspace_paths_resolve_from_explicit_root_for_host_and_device_assets() {
    let (_directory, workspace) = tempdir();
    let resources = workspace.join("resources");
    let source = document(
        &resources,
        r#"
templates:
  workspace-device:
    kind: model
    ready_log: listening
    config: third_party/gem5/device.py
    runtime: {binary: third_party/gem5/bin/device}
    pci: {rom: third_party/gem5-resources/device.rom}
machines:
  - id: m
    vhost:
      use: base
      runtime: {binary: build/qemu/qemu-system-x86_64}
      kernel: third_party/gem5-resources/vmlinux
      initrd: third_party/gem5-resources/initrd
      disks:
        - {id: root, backing: third_party/gem5-resources/root.raw, format: raw}
    devices:
      - {use: workspace-device}
"#,
    );
    let topology = load_with_workspace(&source, &resources, &workspace).unwrap();
    let machine = &topology.machines[0];
    assert_eq!(
        machine.vhost.program.binary,
        workspace
            .join("build/qemu/qemu-system-x86_64")
            .to_string_lossy()
            .into_owned()
    );
    let boot = machine.vhost.boot.as_ref().unwrap();
    assert_eq!(
        boot.kernel,
        workspace.join("third_party/gem5-resources/vmlinux")
    );
    assert_eq!(
        boot.initrd,
        Some(workspace.join("third_party/gem5-resources/initrd"))
    );
    assert_eq!(
        machine.vhost.disks[0].source,
        workspace.join("third_party/gem5-resources/root.raw")
    );
    let device = &machine.devices[0];
    assert_eq!(
        device.program.binary,
        workspace
            .join("third_party/gem5/bin/device")
            .to_string_lossy()
            .into_owned()
    );
    let Adapter::Template(adapter) = &device.adapter else {
        panic!("declared kinds use command templates");
    };
    assert_eq!(
        adapter.config.as_deref(),
        Some(workspace.join("third_party/gem5/device.py").as_path())
    );
    assert_eq!(
        device.pci.rom.as_deref(),
        Some(
            workspace
                .join("third_party/gem5-resources/device.rom")
                .as_path()
        )
    );
}

#[test]
fn workspace_paths_reject_parent_directory_traversal() {
    let (_directory, workspace) = tempdir();
    let resources = workspace.join("resources");
    let source = document(
        &resources,
        r#"
machines:
  - id: m
    vhost:
      use: base
      runtime: {binary: ../outside/qemu}
"#,
    );

    let error = load_with_workspace(&source, &resources, &workspace).unwrap_err();
    assert!(
        format!("{error:#}")
            .contains("workspace-relative paths must not contain parent-directory traversal")
    );
}

#[test]
fn workspace_paths_reject_environment_interpolation() {
    let (_directory, workspace) = tempdir();
    let resources = workspace.join("resources");
    let source = document(
        &resources,
        r#"
machines:
  - id: m
    vhost:
      use: base
      runtime: {binary: "${COSIM_WORKSPACE}/build/qemu/qemu-system-x86_64"}
"#,
    );

    let error = load_with_workspace(&source, &resources, &workspace).unwrap_err();
    assert!(format!("{error:#}").contains("without COSIM_WORKSPACE interpolation"));
}

#[test]
fn imports_templates_and_counts_expand_with_workspace_paths() {
    let (_directory, root) = tempdir();
    let root = root.as_path();
    write(
        root,
        "lib/devices/model.yaml",
        r#"
version: 1
templates:
  accel:
    kind: model
    ready_log: listening
    config: config/model.json
    runtime: {binary: bin/model, env: {MODE: base}}
    memory_regions: [{name: buffer, size: 4M}]
    pci: {rom: firmware/device.rom}
    args: {mode: fast, list: [1, 2]}
"#,
    );
    write(root, "lib/base.yaml", BASE);
    let source = write(
        root,
        "topology.yaml",
        r#"version: 1
imports: [lib/base.yaml, lib/devices/model.yaml]
templates:
  node:
    vhost:
      use: base
      kernel: images/vmlinux
      cmdline: console=ttyS0
      disks: [{id: root, backing: images/root.raw, format: raw}]
    devices:
      - {use: accel, count: 2, args: {list: [3]}, runtime: {env: {EXTRA: "1"}}}
      - {use: accel, id: solo, pci: {rom: images/override.rom}}
machines:
  - {id: n, use: node, count: 3}
"#,
    );
    let topology = load_with_workspace(&source, root, root).unwrap();
    let ids = topology
        .machines
        .iter()
        .map(|machine| machine.id.as_str())
        .collect::<Vec<_>>();
    assert_eq!(ids, ["n0", "n1", "n2"]);
    let machine = &topology.machines[1];
    let devices = machine
        .devices
        .iter()
        .map(|device| device.id.as_str())
        .collect::<Vec<_>>();
    assert_eq!(devices, ["accel-0", "accel-1", "solo"]);
    let device = &machine.devices[0];
    assert_eq!(
        device.program.binary,
        root.join("bin/model").to_str().unwrap()
    );
    assert_eq!(device.program.env["MODE"], "base");
    assert_eq!(device.program.env["EXTRA"], "1");
    let Adapter::Template(adapter) = &device.adapter else {
        panic!("declared kinds use command templates");
    };
    assert_eq!(
        adapter.config.as_deref(),
        Some(root.join("config/model.json").as_path())
    );
    assert_eq!(adapter.args["list"], json!([3]));
    assert_eq!(adapter.args["mode"], "fast");
    assert_eq!(
        device.pci.rom.as_deref(),
        Some(root.join("firmware/device.rom").as_path())
    );
    assert_eq!(
        machine.devices[2].pci.rom.as_deref(),
        Some(root.join("images/override.rom").as_path())
    );
    assert_eq!(machine.vhost.program.binary, "qemu");
    let boot = machine.vhost.boot.as_ref().unwrap();
    assert_eq!(boot.kernel, root.join("images/vmlinux"));
    let disk = &machine.vhost.disks[0];
    assert_eq!(disk.source, root.join("images/root.raw"));
    assert_eq!(
        (disk.format, disk.mode),
        (DiskFormat::Raw, DiskMode::Overlay)
    );
}

#[test]
fn a_machine_can_replace_the_vhost_template_of_its_template() {
    let (_directory, root) = tempdir();
    write(
        &root,
        "lib/other.yaml",
        "version: 1\ntemplates:\n  other: {kind: vhost, runtime: {binary: other-qemu}, \
         memory: 128M, cpus: 2, accel: kvm, machine: virt}\n",
    );
    let source = write(
        &root,
        "topology.yaml",
        "version: 1\nimports: [lib/base.yaml, lib/other.yaml]\ntemplates:\n  \
         node: {vhost: {use: base, memory: 32M}}\nmachines:\n  \
         - {id: m, use: node, vhost: {use: other}}\n",
    );
    write(&root, "lib/base.yaml", BASE);
    let topology = cosim_topology::load(&source, &root).unwrap();
    let vhost = &topology.machines[0].vhost;
    assert_eq!(vhost.program.binary, "other-qemu");
    assert_eq!((vhost.machine.as_str(), vhost.cpus.get()), ("virt", 2));
    assert_eq!(vhost.memory.bytes(), 32 << 20);
}

#[test]
fn import_and_template_errors_name_their_cause() {
    let root = tempfile::tempdir().unwrap();
    let root = root.path();
    write(root, "a.yaml", "version: 1\nimports: [b.yaml]\n");
    write(root, "b.yaml", "version: 1\nimports: [a.yaml]\n");
    let cycle = failure(cosim_topology::load(&root.join("a.yaml"), root));
    assert!(cycle.contains("import cycle"), "{cycle}");

    write(
        root,
        "loop.yaml",
        "version: 1\ntemplates:\n  x: {use: y}\n  y: {use: x}\nmachines: [{id: m, use: x}]\n",
    );
    let template = failure(cosim_topology::load(&root.join("loop.yaml"), root));
    assert!(template.contains("template cycle"), "{template}");

    write(root, "one.yaml", "version: 1\ntemplates: {t: {}}\n");
    write(root, "two.yaml", "version: 1\ntemplates: {t: {}}\n");
    write(
        root,
        "both.yaml",
        "version: 1\nimports: [one.yaml, two.yaml]\n",
    );
    let duplicate = failure(cosim_topology::load(&root.join("both.yaml"), root));
    assert!(duplicate.contains("duplicate template t"), "{duplicate}");

    write(
        root,
        "builtin.yaml",
        "version: 1\nkinds:\n  qemu-device: {role: device, model: qemu, argv: [x]}\n",
    );
    let builtin = failure(cosim_topology::load(&root.join("builtin.yaml"), root));
    assert!(
        builtin.contains("cannot replace built-in kind"),
        "{builtin}"
    );

    write(root, "machines/m.yaml", "version: 1\n");
    write(
        root,
        "vhosts/h.yaml",
        "version: 1\nimports: [machines/m.yaml]\n",
    );
    let layering = failure(cosim_topology::load(&root.join("vhosts/h.yaml"), root));
    assert!(layering.contains("invalid import direction"), "{layering}");

    write(
        root,
        "shared/common.yaml",
        "version: 1\ntemplates: {common: {}}\n",
    );
    write(
        root,
        "shared/left.yaml",
        "version: 1\nimports: [common.yaml]\n",
    );
    write(
        root,
        "shared/right.yaml",
        "version: 1\nimports: [common.yaml]\n",
    );
    let diamond = write(
        root,
        "shared/top.yaml",
        "version: 1\nimports: [left.yaml, right.yaml, ../lib/base.yaml]\nmachines:\n  - {id: m, vhost: {use: base}}\n",
    );
    write(root, "lib/base.yaml", BASE);
    cosim_topology::load(&diamond, root).expect("a shared import is loaded once");
}

#[test]
fn validation_rejects_inconsistent_declarations() {
    let cases = [
        (", extra: 1", "[]", "unknown field `extra`"),
        (", boot: {kernel: image}", "[]", "unknown field `boot`"),
        (
            ", serial: {timeout: 5}",
            "[]",
            "serial.timeout requires serial.wait_for",
        ),
        (
            ", serial: {wait_for: up, timeout: 18446744073709551615}",
            "[]",
            "serial.timeout must be 1..86400 seconds",
        ),
        (", memory: 0", "[]", "byte size out of range"),
        (
            ", memory_align: 3M",
            "[]",
            "alignment must be a power of two",
        ),
        (
            "",
            "[{kind: model, runtime: {binary: m}}]",
            "custom device commands require ready_log",
        ),
        (
            "",
            "[{kind: model, ready_log: up, runtime: {binary: m, argv: [a], command: '[]'}}]",
            "argv and command are mutually exclusive",
        ),
        (", runtime: {command: '{{'}", "[]", "command template"),
        (
            "",
            "[{kind: model, ready_log: up, runtime: {binary: m, argv: [a, '{% if %}']}}]",
            "argv[1] template",
        ),
        (
            "",
            "[{kind: qemu-device, runtime: {binary: q}, args: {device: {}}}]",
            "args.device.driver",
        ),
        (
            "",
            "[{kind: qemu-device, args: {device: {driver: edu}}}]",
            "runtime.binary is required",
        ),
        (
            "",
            "[{kind: qemu-device, runtime: {binary: q}, args: {device: {driver: edu}, bus: x}}]",
            "unknown field `bus`",
        ),
        (
            "",
            "[{kind: gem5-mi300x, config: c, memory_regions: [{name: vram, size: 1G}]}]",
            "requires vhost.memory_map",
        ),
        (
            ", memory_map: '[]'",
            "[{kind: gem5-mi300x, config: c, memory_regions: [{name: vram, size: 3G}]}]",
            "VRAM must be a power of two",
        ),
        (
            "",
            "[{id: Gpu, kind: model, ready_log: up, runtime: {binary: m}}, \
             {id: gpu, kind: model, ready_log: up, runtime: {binary: m}}]",
            "duplicate device gpu",
        ),
        (
            "",
            "[{kind: model, count: 5, ready_log: up, runtime: {binary: m}}]",
            "exceeds 4 devices allowed by vhost kind vhost",
        ),
        ("", "[{kind: missing}]", "unknown device kind missing"),
    ];
    for (vhost, devices, expected) in cases {
        let root = tempfile::tempdir().unwrap();
        let message = failure(machine(root.path(), vhost, devices));
        assert!(
            message.contains(expected),
            "vhost {vhost:?} devices {devices:?}: {message}"
        );
    }
}

#[test]
fn vhost_validation_rejects_inconsistent_declarations() {
    let cases = [
        (
            "disks: [{id: d, path: a, backing: b}]",
            "exactly one of path or backing",
        ),
        (
            "disks: [{id: d, path: a, shared: true}]",
            "shared disks must be readonly",
        ),
        (
            "disks: [{id: d, path: a, readonly: false}]",
            "direct writes require readonly: false and shared: false",
        ),
        (
            "disks: [{id: d, path: a, create: true}]",
            "create: true requires size",
        ),
        (
            "disks: [{id: d, path: a, size: 1M}]",
            "size requires create: true",
        ),
        (
            "disks: [{id: d, path: a, format: vmdk}]",
            "unknown variant `vmdk`",
        ),
        ("cmdline: quiet", "require vhost.kernel or vhost.image"),
    ];
    for (fields, expected) in cases {
        let root = tempfile::tempdir().unwrap();
        let error = failure(machine(root.path(), &format!(", {fields}"), "[]"));
        assert!(error.contains(expected), "vhost {fields:?}: {error}");
    }
}

#[test]
fn guest_hints_require_a_vhost_kernel_or_image() {
    let root = tempfile::tempdir().unwrap();
    let error = failure(machine(
        root.path(),
        "",
        "[{kind: model, ready_log: up, runtime: {binary: m}, guest_hints: {cmdline: quiet}}]",
    ));
    assert!(error.contains("guest_hints.cmdline requires vhost.image or vhost.kernel"));
}

#[test]
fn image_recipe_materializes_a_kernel_and_immutable_root_disk() {
    let root = tempfile::tempdir().unwrap();
    let mut topology = machine(
        root.path(),
        ", image: ubuntu/24.04/x86_64/rocm/7.0, cmdline: console=ttyS0 root=/dev/vda1 rw",
        "[]",
    )
    .unwrap();
    let kernel = root
        .path()
        .join("build/images/ubuntu/24.04/x86_64/rocm/7.0/kernel");
    let disk = root
        .path()
        .join("build/images/ubuntu/24.04/x86_64/rocm/7.0/disk");
    let vhost = &mut topology.machines[0].vhost;
    cosim_topology::materialize_image_recipe(
        vhost,
        Some(kernel.clone()),
        disk.clone(),
        DiskFormat::Qcow2,
    )
    .unwrap();
    assert_eq!(vhost.boot.as_ref().unwrap().kernel, kernel);
    assert_eq!(
        vhost.boot.as_ref().unwrap().cmdline.as_deref(),
        Some("console=ttyS0 root=/dev/vda1 rw")
    );
    assert_eq!(vhost.disks.len(), 1);
    assert_eq!(vhost.disks[0].id.as_str(), "root");
    assert_eq!(vhost.disks[0].source, disk);
    assert_eq!(vhost.disks[0].mode, DiskMode::Overlay);
    assert!(vhost.disks[0].boot);
}

#[test]
fn vhost_image_is_a_recipe_path_not_an_object() {
    let root = tempfile::tempdir().unwrap();
    let error = failure(machine(
        root.path(),
        ", image: {recipe: ubuntu/24.04/x86_64/rocm/7.0}",
        "[]",
    ));
    assert!(error.contains("invalid type"), "{error}");
}

#[test]
fn image_recipe_rejects_disk_ids_that_differ_only_by_ascii_case() {
    let root = tempfile::tempdir().unwrap();
    let mut topology = machine(
        root.path(),
        ", image: ubuntu/24.04/x86_64/rocm/7.0, disks: [{id: ROOT, path: existing.qcow2}]",
        "[]",
    )
    .unwrap();
    let error = cosim_topology::materialize_image_recipe(
        &mut topology.machines[0].vhost,
        None,
        root.path()
            .join("build/images/ubuntu/24.04/x86_64/rocm/7.0/disk"),
        DiskFormat::Qcow2,
    )
    .unwrap_err()
    .to_string();

    assert!(error.contains("conflicts with vhost disk root"), "{error}");
}

#[test]
fn disk_modes_follow_access_and_snapshot_declarations() {
    let root = tempfile::tempdir().unwrap();
    let topology = machine(
        root.path(),
        ", snapshot: false, disks: [{id: base, backing: a}, {id: plain, path: b}, {id: ro, path: c, readonly: true}, {id: rw, path: d, readonly: false, shared: false}, {id: new, path: e, create: true, size: 1M, readonly: false, shared: false}]",
        "[]",
    )
    .unwrap();
    let modes = topology.machines[0]
        .vhost
        .disks
        .iter()
        .map(|disk| (disk.id.as_str(), disk.mode))
        .collect::<Vec<_>>();
    assert_eq!(
        modes,
        [
            ("base", DiskMode::Overlay),
            ("plain", DiskMode::Overlay),
            ("ro", DiskMode::ReadOnly),
            ("rw", DiskMode::Direct),
            ("new", DiskMode::Direct),
        ]
    );
    let root = tempfile::tempdir().unwrap();
    let topology = machine(
        root.path(),
        ", snapshot: true, disks: [{id: rw, path: d, readonly: false, shared: false}]",
        "[]",
    )
    .unwrap();
    assert_eq!(topology.machines[0].vhost.disks[0].mode, DiskMode::Overlay);
}

#[test]
fn shared_images_reject_direct_writers_and_conflicting_creation() {
    let root = tempfile::tempdir().unwrap();
    let direct = document(
        root.path(),
        "machines:\n  - id: m\n    count: 2\n    vhost: {use: base, disks: [{id: d, path: /images/a, readonly: false, shared: false}]}\n",
    );
    let message = failure(cosim_topology::load(&direct, root.path()));
    assert!(message.contains("written directly"), "{message}");
    let readers = document(
        root.path(),
        "machines:\n  - id: m\n    count: 2\n    vhost: {use: base, disks: [{id: d, path: /images/a, readonly: true}]}\n",
    );
    cosim_topology::load(&readers, root.path()).expect("readers may share an image");
    let creators = document(
        root.path(),
        "machines:\n  - id: a\n    vhost: {use: base, disks: [{id: d1, path: /images/n, create: true, size: 1M, readonly: true}]}\n  - id: b\n    vhost: {use: base, disks: [{id: d2, path: /images/n, create: true, size: 2M, readonly: true}]}\n",
    );
    let message = failure(cosim_topology::load(&creators, root.path()));
    assert!(message.contains("conflicting creation"), "{message}");
}

#[test]
fn memory_layout_aligns_regions_to_page_and_declared_alignment() {
    let root = tempfile::tempdir().unwrap();
    let topology = machine(
        root.path(),
        ", memory: 3M, memory_align: 2M",
        "[{id: a, kind: model, ready_log: up, runtime: {binary: m}, memory_regions: \
         [{name: buffer, size: 4096, align: 1G}, {name: tail, size: 8K, align: 4096}]}]",
    )
    .unwrap();
    let machine = &topology.machines[0];
    let layout = machine.memory_layout(page()).unwrap();
    assert_eq!((layout.ram.offset, layout.ram.size), (0, 3 << 20));
    let regions = layout.regions_of(&machine.devices[0].id);
    assert_eq!((regions[0].offset, regions[0].size), (1 << 30, 4096));
    assert_eq!(regions[1].offset, (1 << 30) + 4096);
    assert_eq!(layout.size, (1 << 30) + 4096 + 8192);

    let large_page = PageSize::new(65536).unwrap();
    let message = failure(machine.memory_layout(large_page));
    assert!(
        message.contains("multiple of the 65536-byte page size"),
        "{message}"
    );
    assert!(PageSize::new(4097).is_err());

    let root = tempfile::tempdir().unwrap();
    let topology = machine_overflow(root.path());
    let message = failure(topology.machines[0].memory_layout(page()));
    assert!(
        message.contains("overflow") || message.contains("maximum file size"),
        "{message}"
    );
}

fn machine_overflow(root: &Path) -> Topology {
    machine(
        root,
        ", memory: 4611686018427387904",
        "[{id: a, kind: model, ready_log: up, runtime: {binary: m}, memory_regions: \
         [{name: buffer, size: 4611686018427387904, align: 4611686018427387904}]}]",
    )
    .unwrap()
}

#[test]
fn guest_memory_maps_split_platform_holes_and_reject_invalid_ranges() {
    let topology =
        cosim_topology::load(&resources().join("machines/gpu-8.yaml"), &resources()).unwrap();
    let layout = topology.machines[0].memory_layout(page()).unwrap();
    let ranges = layout
        .guest_ranges
        .iter()
        .map(|range| (range.start, range.size, range.offset))
        .collect::<Vec<_>>();
    assert_eq!(ranges, [(0, 2 << 30, 0), (4 << 30, 30 << 30, 2 << 30)]);
    let topology = cosim_topology::load(
        &resources().join("machines/gem5-aarch64.yaml"),
        &resources(),
    )
    .unwrap();
    let layout = topology.machines[0].memory_layout(page()).unwrap();
    assert_eq!(layout.guest_ranges[0].start, 1 << 30);

    for (map, expected) in [
        (
            r#"'[{"start": 0, "size": "32M"}, {"start": 16777216, "size": "32M"}]'"#,
            "overlap",
        ),
        (
            r#"'[{"start": 0, "size": "32M"}]'"#,
            "cover exactly vhost.memory",
        ),
        (r#"'[{"start": 1, "size": "64M"}]'"#, "page size"),
        ("'{{ missing }}'", "render vhost.memory_map"),
    ] {
        let root = tempfile::tempdir().unwrap();
        let topology = machine(root.path(), &format!(", memory_map: {map}"), "[]").unwrap();
        let message = failure(topology.machines[0].memory_layout(page()));
        assert!(message.contains(expected), "{map}: {message}");
    }
}

/// Session paths for a machine, as a planner would assign them.
struct Paths {
    pool: PathBuf,
    run: PathBuf,
}

impl Paths {
    fn new() -> Self {
        Self {
            pool: PathBuf::from("/pool,dir/m0/pool"),
            run: PathBuf::from("/run,dir"),
        }
    }

    fn device(&self, machine: &Machine, id: &str) -> [PathBuf; 4] {
        let base = self.run.join(machine.id.as_str());
        [
            base.join(format!("{id}.sock")),
            base.join(format!("{id}.qmp.sock")),
            base.join(id).join("output.log"),
            base.join(id),
        ]
    }
}

#[test]
fn builtin_adapters_render_pool_offsets_and_readiness() {
    let topology = cosim_topology::load(
        &resources().join("machines/mixed-models.yaml"),
        &resources(),
    )
    .unwrap();
    let machine = &topology.machines[0];
    let layout = machine.memory_layout(page()).unwrap();
    let paths = Paths::new();

    let gem5 = &machine.devices[1];
    let [socket, qmp, log, node] = paths.device(machine, gem5.id.as_str());
    let context = DeviceContext {
        machine,
        layout: &layout,
        pool: &paths.pool,
        socket: &socket,
        qmp: &qmp,
        output_log: &log,
        node_dir: &node,
        run_dir: &paths.run,
    };
    let launch = gem5.launch(&context).unwrap();
    let vram = &layout.regions_of(&gem5.id)[0];
    assert_eq!(vram.offset, (8 << 30) + (16 << 30));
    for expected in [
        format!("--pool-vram-offset={}", vram.offset),
        format!("--dgpu-mem-size={}B", 16u64 << 30),
        format!("--shared-pool={}", paths.pool.display()),
        format!(
            "--host-memory-ranges={}",
            serde_json::to_string(&layout.guest_ranges).unwrap()
        ),
        "--num-compute-units=40".to_owned(),
    ] {
        assert!(
            launch.argv.contains(&expected),
            "missing {expected}: {:?}",
            launch.argv
        );
    }
    let config = launch
        .argv
        .iter()
        .position(|arg| arg.ends_with("mi300_cosim.py"))
        .unwrap();
    let listener = launch
        .argv
        .iter()
        .position(|arg| arg == "--listener-mode=off")
        .unwrap();
    assert!(
        listener < config,
        "gem5 options precede the configuration script"
    );
    assert_eq!(
        launch.probes,
        [
            Probe::Log {
                path: log.clone(),
                marker: format!(
                    "MI300XVfioUser: listening on {} (vfio-user protocol)",
                    socket.display()
                ),
                timeout: None,
            },
            Probe::Socket {
                path: socket.clone()
            },
        ]
    );

    let edu = &machine.devices[2];
    let [socket, qmp, log, node] = paths.device(machine, edu.id.as_str());
    let context = DeviceContext {
        socket: &socket,
        qmp: &qmp,
        output_log: &log,
        node_dir: &node,
        ..context
    };
    let launch = edu.launch(&context).unwrap();
    let qmp_text = format!(
        "unix:{},server=on,wait=off",
        qmp.display().to_string().replace(',', ",,")
    );
    assert!(launch.argv.contains(&qmp_text), "{:?}", launch.argv);
    let server: serde_json::Value = serde_json::from_str(launch.argv.last().unwrap()).unwrap();
    assert_eq!(server["device"], "device0");
    assert_eq!(server["socket"]["path"], json!(socket));
    assert_eq!(
        launch.probes,
        [Probe::Socket { path: socket }, Probe::Qmp { path: qmp }]
    );
}

#[test]
fn template_devices_receive_region_offsets_and_configuration() {
    let (_directory, root) = tempdir();
    let topology = machine(
        &root,
        "",
        "[{id: a, kind: model, ready_log: up, config: model.json, args: {mode: fast}, \
         runtime: {binary: m}, memory_regions: [{name: buffer, size: 8K, align: 4096}]}]",
    )
    .unwrap();
    let machine = &topology.machines[0];
    let layout = machine.memory_layout(page()).unwrap();
    let paths = Paths::new();
    let [socket, qmp, log, node] = paths.device(machine, "a");
    let launch = machine.devices[0]
        .launch(&DeviceContext {
            machine,
            layout: &layout,
            pool: &paths.pool,
            socket: &socket,
            qmp: &qmp,
            output_log: &log,
            node_dir: &node,
            run_dir: &paths.run,
        })
        .unwrap();
    assert_eq!(
        launch.argv,
        [
            root.join("model.json").to_str().unwrap(),
            socket.to_str().unwrap(),
            &(64u64 << 20).to_string(),
            "fast",
        ]
    );
}

#[test]
fn resource_vhost_template_attaches_devices_behind_root_ports() {
    let resource_root = resources();
    let workspace = fs::canonicalize(resource_root.parent().unwrap()).unwrap();
    let mut topology = cosim_topology::load(
        &resource_root.join("machines/mixed-models.yaml"),
        &resource_root,
    )
    .unwrap();
    let image_dir = workspace.join("build/images/ubuntu/24.04/x86_64/rocm/7.0");
    cosim_topology::materialize_image_recipe(
        &mut topology.machines[0].vhost,
        Some(image_dir.join("kernel")),
        image_dir.join("disk"),
        DiskFormat::Qcow2,
    )
    .unwrap();
    let machine = &topology.machines[0];
    let layout = machine.memory_layout(page()).unwrap();
    let paths = Paths::new();
    let sockets = machine
        .devices
        .iter()
        .map(|device| paths.device(machine, device.id.as_str())[0].clone())
        .collect::<Vec<_>>();
    let vhost_dir = paths.run.join("m0/vhost");
    let overlay = paths.run.join("m0/root.qcow2");
    let disk = &machine.vhost.disks[0];
    let launch = machine
        .vhost
        .launch(&VhostContext {
            machine,
            layout: &layout,
            pool: &paths.pool,
            qmp: &paths.run.join("m0/qmp.sock"),
            serial: &paths.run.join("m0/serial.sock"),
            serial_log: &vhost_dir.join("serial.log"),
            node_dir: &vhost_dir,
            run_dir: &paths.run,
            boot: machine.vhost.boot.as_ref(),
            disks: vec![VhostDisk {
                disk,
                path: &overlay,
                format: DiskFormat::Qcow2,
                readonly: false,
            }],
            devices: machine
                .devices
                .iter()
                .zip(&sockets)
                .map(|(device, socket)| VhostDevice { device, socket })
                .collect(),
        })
        .unwrap();
    let devices = launch
        .argv
        .windows(2)
        .filter(|pair| pair[0] == "-device")
        .map(|pair| serde_json::from_str::<serde_json::Value>(&pair[1]).unwrap())
        .collect::<Vec<_>>();
    let ports = devices
        .iter()
        .filter(|device| device["driver"] == "pcie-root-port")
        .map(|device| (device["addr"].clone(), device["multifunction"].clone()))
        .collect::<Vec<_>>();
    assert_eq!(
        ports,
        [
            (json!("10.0"), json!(true)),
            (json!("10.1"), json!(false)),
            (json!("10.2"), json!(false)),
            (json!("10.3"), json!(false)),
        ]
    );
    let clients = devices
        .iter()
        .filter(|device| device["driver"] == "vfio-user-pci")
        .map(|device| (device["bus"].clone(), device["socket"]["path"].clone()))
        .collect::<Vec<_>>();
    assert_eq!(clients[3], (json!("rp3"), json!(sockets[3])));
    let kernel = launch.argv.iter().position(|arg| arg == "-kernel").unwrap();
    assert!(launch.argv[kernel + 1].ends_with("build/images/ubuntu/24.04/x86_64/rocm/7.0/kernel"));
    let append = launch.argv.iter().position(|arg| arg == "-append").unwrap();
    assert!(launch.argv[append + 1].starts_with("console=ttyS0"));
    let blockdev = launch
        .argv
        .iter()
        .position(|arg| arg == "-blockdev")
        .unwrap();
    let file: serde_json::Value = serde_json::from_str(&launch.argv[blockdev + 1]).unwrap();
    assert_eq!(file["filename"], json!(overlay));
}

#[test]
fn repository_resources_render_every_process() {
    for directory in ["machines", "clusters"] {
        for entry in fs::read_dir(resources().join(directory)).unwrap() {
            let path = entry.unwrap().path();
            let topology = cosim_topology::load(&path, &resources())
                .unwrap_or_else(|error| panic!("{}: {error:#}", path.display()));
            for machine in &topology.machines {
                let layout = machine.memory_layout(page()).unwrap();
                let paths = Paths::new();
                let mut sockets = Vec::new();
                for device in &machine.devices {
                    let [socket, qmp, log, node] = paths.device(machine, device.id.as_str());
                    device
                        .launch(&DeviceContext {
                            machine,
                            layout: &layout,
                            pool: &paths.pool,
                            socket: &socket,
                            qmp: &qmp,
                            output_log: &log,
                            node_dir: &node,
                            run_dir: &paths.run,
                        })
                        .unwrap_or_else(|error| panic!("{}: {error:#}", path.display()));
                    sockets.push(socket);
                }
                let vhost_dir = paths.run.join("vhost");
                machine
                    .vhost
                    .launch(&VhostContext {
                        machine,
                        layout: &layout,
                        pool: &paths.pool,
                        qmp: &paths.run.join("qmp.sock"),
                        serial: &paths.run.join("serial.sock"),
                        serial_log: &vhost_dir.join("serial.log"),
                        node_dir: &vhost_dir,
                        run_dir: &paths.run,
                        boot: None,
                        disks: Vec::new(),
                        devices: machine
                            .devices
                            .iter()
                            .zip(&sockets)
                            .map(|(device, socket)| VhostDevice { device, socket })
                            .collect(),
                    })
                    .unwrap_or_else(|error| panic!("{}: {error:#}", path.display()));
            }
        }
    }
    let schema = serde_json::to_value(cosim_topology::schema()).unwrap();
    assert!(schema["properties"]["machines"].is_object());
}

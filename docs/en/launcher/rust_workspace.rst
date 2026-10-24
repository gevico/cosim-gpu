.. SPDX-License-Identifier: Apache-2.0

.. _launcher-rust-workspace:

Rust workspace
===============

This page describes the crate split, module responsibilities, public interfaces and extension points of the launcher for readers who change the launcher or add a device model.

Workspace Layout
-----------------

The workspace contains the ``cosim-topology``, ``cosim-runtime`` and ``cosim-cli`` crates. ``cosim-cli`` depends on the other two, and ``cosim-runtime`` depends on ``cosim-topology``. The dependency direction encodes the rule that document parsing does not touch the host while only execution logic does.

.. mermaid::

   flowchart TD
       C[cosim-cli] --> T[cosim-topology]
       C --> R[cosim-runtime]
       R --> T

Module Responsibilities
------------------------

.. list-table::
   :header-rows: 1

   * - Path
     - Responsibility
   * - ``crates/cosim-cli/src/main.rs``
     - Clap subcommands, signal escalation, the standard-input lifeline, event output and the verdict line.
   * - ``crates/cosim-topology/src/raw.rs``, ``model.rs``, ``size.rs``
     - Decoded input types, validated types (``Topology``, ``Machine``, ``Vhost``, ``Device``, ``Disk``) and ``ByteSize``.
   * - ``crates/cosim-topology/src/loader.rs``, ``resolve.rs``
     - Imports, merge keys, template inheritance, workspace-relative resource paths, count expansion and validation.
   * - ``crates/cosim-topology/src/adapter/``
     - The ``Adapter`` enum with the ``gem5-mi300x``, ``qemu-device`` and template adapters, host rendering and ``Probe``.
   * - ``crates/cosim-topology/src/layout.rs``
     - Memory pools and guest physical ranges for a given ``PageSize``.
   * - ``crates/cosim-runtime/src/env.rs``, ``layout.rs``, ``plan.rs``
     - ``ExecEnv``, ``SessionLayout`` and the serializable ``Plan``.
   * - ``crates/cosim-runtime/src/session.rs``, ``node.rs``, ``probe.rs``
     - Session resources, node type states, dependency leases, readiness probes and the verdict.
   * - ``crates/cosim-runtime/src/process.rs``, ``resource.rs``, ``disk.rs``, ``manifest.rs``
     - Process groups, file and lock owners, image creation and overlays, and ``clean`` after abnormal exits.

Public Interfaces
------------------

- ``cosim-topology`` exposes ``load``, ``graph`` and ``schema``. Validated types render launch arguments from ``DeviceContext`` and ``VhostContext``.
- ``cosim-runtime`` exposes ``plan``, ``run``, ``clean``, ``check_assets``, ``RunOptions``, ``Shutdown`` and ``Event``.
- ``Plan`` records programs, arguments, environments, dependencies, readiness probes, shared memory regions, disk targets and lock paths; ``cosim run --dry-run`` prints it.

Extension Points: Adapters and Command Templates
-------------------------------------------------

- The device adapter is expressed by the ``Adapter`` enum: ``gem5-mi300x`` runs one GPU per process, ``qemu-device`` exports a QEMU functional device, and the template adapter renders a command from YAML.
- Readiness is expressed by ``Probe``: log markers, Unix socket existence and QMP negotiation. An adapter returns these probes in evaluation order.
- vHost kinds render QEMU arguments from a YAML ``command`` template. A kind declared under ``kinds`` with ``role: device`` provides ``argv`` or ``command`` and requires ``ready_log``.
- ``runtime.argv`` or ``runtime.command`` can replace the command of any device adapter, but the replacement must provide its own readiness contract and resource behavior.
- ``gem5-mi300x`` requires ``config``, exactly one ``vram`` region whose size is a power of two, and MI300X PCI metadata. ``num_compute_units`` ranges from 1 to 1024 and defaults to 40.
- ``qemu-device`` requires ``args.device.driver``, defaults ``id`` to ``device0``, accepts no private memory regions and needs ``runtime.binary``.

Adding a Model
---------------

1. Add a template under ``resources/devices/`` declaring the ``kind``, ``config`` or ``runtime``, memory regions and PCI metadata.
2. Use a built-in adapter, or declare a template kind under ``kinds`` with ``role: device`` and provide its command and ``ready_log``.
3. Add a machine sample under ``resources/machines/`` that uses the template, then run ``cosim validate`` and ``cosim run --dry-run`` to check the rendering.
4. If the model needs a new readiness condition or argument semantics, change ``crates/cosim-topology/src/adapter/`` and add Rust tests.

Dependencies and Safety Rules
------------------------------

- YAML syntax and merge keys use ``serde_yaml_ng``; Serde performs typed decoding.
- MiniJinja renders argument templates, Schemars produces JSON Schema, and ``parse-size`` parses size expressions.
- Tokio runs the session on one thread, ``futures-util`` drives the process nodes concurrently, and ``nix`` provides process-group signals, page size and filesystem statistics.
- Project Rust crates inherit ``unsafe_code = "forbid"`` from the workspace. Device models enter through the adapter boundary; the launcher does not touch model internals directly.
- Checks: ``just check-cosim`` runs formatting, clippy and unit tests; ``just test-cosim-integration`` runs integration tests with real processes and disks.

Sources
--------

- Crate manifests and dependencies: ``crates/cosim-cli/Cargo.toml``, ``crates/cosim-runtime/Cargo.toml`` and ``crates/cosim-topology/Cargo.toml``.
- Adapter implementations: ``crates/cosim-topology/src/adapter/gem5.rs``, ``qemu_device.rs`` and ``template.rs``.
- Runtime exports: ``crates/cosim-runtime/src/lib.rs``.
- Rust guidelines: ``docs/en/contributing/rust_guidelines.rst``.

Related Pages
--------------

- :doc:`yaml_pipeline` for the role of adapters while planning.
- :ref:`ref-device-adapters` for the canonical device adapter contract.
- :ref:`arch-components` for the system view of components and responsibilities.
- :ref:`contrib-rust-guidelines` for Rust code and commit conventions.

.. SPDX-License-Identifier: Apache-2.0

.. _launcher-yaml-pipeline:

YAML pipeline
==============

This page follows a topology YAML document through imports, template merging, validation and memory layout into a plan for the local system. The field reference lives in chapter 6.

Pipeline Overview
------------------

.. mermaid::

   flowchart LR
       Y[Top-level YAML document] --> L[Imports and template merging]
       L --> V[Validation and identifier expansion]
       V --> M[Memory layout]
       M --> P[ExecEnv and SessionLayout]
       P --> J[plan JSON]

``cosim-topology`` reads only YAML documents, so its result does not depend on the system that will run them. ``cosim-runtime`` adds host facts and session paths before producing the plan, and ``run`` is the subcommand that creates resources.

Topology document
-----------------

A top-level document contains ``version: 1`` and any of ``imports``,
``templates``, ``kinds`` and ``machines``. Unknown fields are errors. Each
machine contains its own ``vhost`` mapping, including image, direct-boot and
storage fields.

.. code-block:: yaml

   version: 1
   imports:
     - vhosts/qemu.yaml
     - devices/gpu/mi300x.yaml
   machines:
     - id: m0
       vhost: {use: vhost-x86, memory: 32G}
       devices:
         - {use: mi300x, count: 2}

Imports and Template Expansion
-------------------------------

- Imports resolve first against the importing file, then against the ``--resources`` directory (default ``resources/``). The ``#templates`` suffix is accepted.
- Imported files contribute templates, kinds and further imports; only the top-level document contributes runnable machines.
- ``use`` selects a template. Mappings merge recursively, sequences are replaced and explicit values override template values.
- Import cycles, template cycles, duplicate template or kind names and unknown references are errors. A file reached through several imports is loaded once.
- Inside ``resources/``, ``vhosts/`` and ``devices/`` import nothing, ``machines/`` imports both, and ``clusters/`` imports ``machines/``.

Validation and Identifiers
---------------------------

- Identifiers use 1 to 48 letters, digits, underscores and hyphens; machine, device and disk identifiers must differ in more than ASCII case.
- ``count`` expands ``id: m, count: 4`` into ``m0`` to ``m3``. A topology may contain at most 4096 machines.
- The machine identifier ``memory`` and the device identifiers ``vhost``, ``qmp`` and ``serial`` are reserved by the session layout.
- A machine may not exceed the ``max_devices`` of its vHost kind (``qemu-vhost`` declares 64).
- ``placement.agent`` can describe remote placement, but ``cosim run`` rejects remote placement before allocating resources.
- Resource paths are relative to the workspace root and cannot contain ``..``; absolute paths are accepted. Executable names without a ``/`` are searched in ``PATH`` while planning.

Memory Layout
--------------

Each machine owns one pool file: guest RAM comes first and device regions follow in declaration order. Sizes accept integers or binary units such as ``32G`` and must be multiples of the execution page size; alignments are powers of two of at least one page, with a default of 2 MiB.

For a 32 GiB vHost with eight 8 GiB VRAM regions the pool is 96 GiB, with ``mi300x-0.vram`` at 32 GiB and ``mi300x-7.vram`` at 88 GiB. The name, offset and size of every region are recorded in ``layout.json`` in the session directory.

Producing the Plan
-------------------

- ``ExecEnv`` records the page size, an absolute ``PATH`` and the disk lock directory (``COSIM_DISK_LOCK_DIR``, default ``~/.cache/cosim-gpu/disk-locks``).
- ``SessionLayout`` names every session path: the run directory defaults to ``.cosim/<name>``, and on Linux the pool directory defaults to ``/dev/shm/cosim-<name>-<hash>``.
- The plan records executables, arguments, environments, dependencies, readiness probes, shared memory regions, disk targets and lock paths. Each device precedes its host in process order.
- ``validate`` and ``plan`` only parse and render; ``run`` creates the run directory, the memory pools and the disk overlays.
- Device commands are rendered by an adapter: ``gem5-mi300x`` produces gem5 arguments, ``qemu-device`` produces QEMU ``x-remote`` arguments, and template kinds render the YAML command.

Sources
--------

- Imports, merging and validation: ``crates/cosim-topology/src/loader.rs`` and ``resolve.rs``.
- Memory layout: ``crates/cosim-topology/src/layout.rs``.
- Host environment and plan: ``crates/cosim-runtime/src/env.rs``, ``layout.rs`` and ``plan.rs``.
- Device adapters: ``crates/cosim-topology/src/adapter/``.
- Samples: ``resources/machines/single-gpu.yaml`` and ``resources/vhosts/qemu.yaml``.

Related Pages
--------------

- :doc:`cli` for commands and options.
- :doc:`session_lifecycle` for how the plan is executed and supervised.
- :ref:`topo-write-topology` for writing topology YAML.
- :ref:`ref-topology-schema` for fields, types and defaults.
- :ref:`ref-device-adapters` for the device adapter contract.

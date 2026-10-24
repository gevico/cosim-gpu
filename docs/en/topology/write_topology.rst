.. SPDX-License-Identifier: Apache-2.0


.. _topo-write-topology:

Writing topologies
==================

This page walks through writing a topology document: start from the document skeleton, reuse host and device definitions through imports and templates, expand machine and device counts, and check the result with ``validate``, ``plan`` and ``graph``. The complete field set and defaults are in :ref:`ref-topology-schema`.

Document skeleton
-----------------

A topology document is always ``version: 1`` and may contain ``imports``, ``templates``, ``kinds`` and ``machines``. Unknown fields are errors.

.. code-block:: yaml

   version: 1
   imports:
     - vhosts/qemu.yaml
     - devices/gpu/mi300x.yaml
     - devices/pci/qemu-edu.yaml
   machines:
     - id: m0
       vhost: {use: vhost-x86, memory: 32G}
       devices:
         - {use: mi300x, count: 2}
         - {use: qemu-edu, count: 2}

- Each machine's ``vhost`` owns its image, ``kernel``, ``initrd``, ``cmdline``
  and ``disks`` fields.
- ``cosim schema`` prints the JSON Schema of the complete topology format.
- Resource paths resolve against the workspace root, including executables
  containing ``/``, device ``config`` and ``pci.rom``, vHost ``kernel`` and
  ``initrd``, and disk ``path`` and ``backing``. A bare executable name is
  looked up in ``PATH`` while planning.

Imports and templates
---------------------

- Imports resolve against the importing file, then against the ``--resources`` directory (default ``resources/``); the ``#templates`` suffix is accepted.
- Imported files contribute templates, kinds and further imports; only the top-level document contributes runnable machines.
- ``use`` selects a template; mappings merge recursively, sequences are replaced, and explicit values override template values.
- Import cycles, template cycles, duplicate template or kind names and unknown references are errors; a file reached through several imports is loaded once.
- The repository layout convention: ``resources/vhosts/`` and ``resources/devices/`` import nothing, ``resources/machines/`` imports both, and ``resources/clusters/`` imports machine files.

These four configuration directories are siblings under ``resources/``.
``samples/`` is reserved for programs run after a vHost boots; configuration
files belong under ``resources/``.

.. code-block:: text

   vhosts/ ──┐
   devices/ ─┴──> machines/ ───> clusters/

Machines, devices and count
---------------------------

- ``count`` expands ``id: m, count: 4`` into ``m0`` to ``m3``; a topology holds at most 4096 machines.
- Device identifiers default to the ``use`` name or kind plus an index, such as ``mi300x-0``; an explicit ``id`` is kept when count is one.
- Identifiers use 1 to 48 letters, digits, underscores and hyphens; machine, device and disk identifiers must differ in more than ASCII case.
- The machine identifier ``memory`` and the device identifiers ``vhost``, ``qmp`` and ``serial`` are reserved by the session layout.
- A machine may not exceed the ``max_devices`` of its vHost kind; ``qemu-vhost`` declares 64.
- ``placement.agent`` is parsed and stored only; ``cosim run`` rejects remote placement.

vHost and device fields
-----------------------

A vHost declares ``kind``, ``runtime.binary``, ``runtime.env``, ``memory``,
``cpus``, ``accel`` and the QEMU ``machine``. Optional fields include its
image and direct-boot inputs. A device ``kind`` selects the launch contract:

.. list-table::
   :header-rows: 1

   * - kind
     - Purpose
     - Required fields
   * - ``gem5-mi300x``
     - gem5 MI300X performance model
     - ``config``, exactly one power-of-two ``vram`` region, and the host ``memory_map``
   * - ``qemu-device``
     - QEMU device exported over vfio-user
     - ``runtime.binary`` and ``args.device.driver``; rejects ``config`` and private memory regions
   * - Declared device kind
     - Custom launch command (extension point)
     - ``role: device`` plus ``argv`` or ``command`` under ``kinds``; ``ready_log``

The complete field tables and adapter contracts are in :ref:`ref-topology-schema` and :ref:`ref-device-adapters`; vHost profiles are in :doc:`hosts/index`, device kinds in :doc:`devices/index`.

vHost images and disks
----------------------

The ``vhost`` mapping may select ``image`` or declare ``kernel``, ``initrd``
and ``cmdline`` directly. It also owns ``disks`` and ``snapshot``. The write
mode of a disk follows its declaration:

.. list-table::
   :header-rows: 1

   * - Declaration
     - Behavior
   * - ``readonly: true``
     - Opens the source image read-only
   * - ``readonly: false`` plus ``shared: false``
     - Writes ``path`` directly; with ``backing`` declared or vHost ``snapshot: true``, uses a per-machine qcow2 overlay instead
   * - No ``readonly``
     - Writes a per-machine qcow2 overlay in the session directory; ``shared: true`` requires ``readonly: true``
   * - ``create: true`` plus ``size``
     - Creates a missing ``path`` with ``qemu-img``; formats under a temporary name and publishes it with a link
   * - Several disks referencing one path
     - A direct writer cannot share its image with other disks; creation requests must agree on size and format

The authoritative vHost and disk field descriptions are in :ref:`ref-topology-schema`.

Validating, previewing and running
----------------------------------

.. code-block:: bash

   # Check structure, identifiers and memory layout; --assets also checks local files
   just run-cli validate resources/machines/gpu-8.yaml  --assets
   # Print executables, arguments, environment, readiness probes, memory layout and disk targets
   just run-topology resources/machines/mixed-models.yaml --dry-run
   # Print a Mermaid graph of machines and vfio-user edges
   just run-cli graph resources/clusters/cluster-4x8.yaml
   # Print the JSON Schema of the format
   just run-cli schema
   # Start a session
   just run-topology resources/machines/single-gpu.yaml

- ``validate`` starts no processes; ``plan`` prints the plan that ``run`` executes; ``graph`` only reads the document.
- ``--assets`` and a real session start check that files such as ``runtime.binary``, ``config`` and ``pci.rom`` exist.
- Starting a session requires Linux glibc and ``setpriv``; other systems use the development container, see :ref:`gs-platform-container`.

Sources and evidence
--------------------

- Parsing and validation: ``crates/cosim-topology/src/raw.rs``, ``crates/cosim-topology/src/resolve.rs``, ``crates/cosim-topology/src/model.rs``.
- Planning and layout: ``crates/cosim-topology/src/layout.rs``, ``crates/cosim-runtime/src/plan.rs``.
- Command entry point and options: ``crates/cosim-cli/src/main.rs``.
- Runnable samples: ``resources/machines/``, ``resources/clusters/``.

Related pages
-------------

- Single and multi-machine: :doc:`single_machine`, :doc:`multi_machine`
- Machine catalog: :doc:`machines/index`
- vHosts and devices: :doc:`hosts/index`, :doc:`devices/index`
- vHost: :ref:`ref-topology-schema`
- Schema reference: :ref:`ref-topology-schema`

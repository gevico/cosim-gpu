.. SPDX-License-Identifier: Apache-2.0


.. _topo-vhosts:

vHost profiles
==============

Every machine has one QEMU vHost process. Its template renders YAML fields
into a QEMU command line, binds the memory pool, and exposes QMP and serial.

Role in a topology
------------------

- A machine has exactly one vHost; its kind must use ``model: qemu``, and the repository ships only ``qemu-vhost``.
- ``resources/vhosts/qemu.yaml`` declares ``qemu-vhost``: the command template renders with MiniJinja, binds the memory pool, exposes QMP and the serial console, gives every device its own PCIe root port at slots ``0x10`` to ``0x17`` (eight functions), and lets QEMU place disks in the remaining slots.
- The kind declares ``max_devices: 64``; a machine may not exceed that number of devices.
- The vHost starts only after every local device is ready and has handed over its lease; devices stop after the vHost has shut down.
- Every vHost program must stay in the foreground, keep its resource users in its process group and keep inherited file descriptors open; QEMU ``-daemonize`` is rejected.

vHost fields
------------

.. list-table::
   :header-rows: 1

   * - Field
     - Type
     - Default
     - Description
   * - ``kind``
     - string
     - none
     - Must resolve to a vHost kind with ``model: qemu``
   * - ``runtime.binary``
     - path or name
     - none
     - Relative to the workspace root; a bare name is looked up in ``PATH``
   * - ``runtime.env``
     - map
     - ``{}``
     - Processes additionally receive only ``PATH`` and ``LANG=C``
   * - ``memory``
     - byte size
     - none
     - Must be a multiple of the execution page size
   * - ``cpus``
     - positive integer
     - none
     - Passed to QEMU ``-smp``
   * - ``accel``
     - string
     - none
     - For example ``kvm`` or ``tcg``
   * - ``machine``
     - string
     - none
     - QEMU machine type, for example ``q35``
   * - ``cpu``
     - string
     - none
     - Passed to ``-cpu``
   * - ``display``, ``monitor``
     - string
     - none
     - QEMU backends; the samples use ``none``
   * - ``no_reboot``
     - bool
     - ``false``
     - Adds ``-no-reboot``
   * - ``memory_align``
     - byte size
     - 2 MiB
     - Power of two; also the default alignment of device regions
   * - ``memory_map``
     - MiniJinja template
     - none
     - Required when the machine has a gem5-mi300x device
   * - ``serial.wait_for``, ``serial.timeout``
     - string, 1 to 86400 seconds
     - none, the session ``--ready-timeout``
     - Serial readiness marker and deadline
   * - ``args``
     - list
     - ``[]``
     - Appended to the end of the QEMU command line

Shipped profiles
----------------

The six profiles are defined under ``resources/vhosts/`` and selected by a machine through ``use``.

.. _topo-vhost-x86:

vhost-x86
~~~~~~~~~

- ``q35``, ``kvm``, ``host`` CPU, 8 GiB RAM, 4 vCPU; binary ``build/qemu/qemu-system-x86_64``.
- ``memory_map`` describes the x86_64 PCI hole: when RAM is at least 2.75 GiB, 2 GiB stay below 4 GiB and the rest goes above 4 GiB.
- Provides the base x86_64 KVM runtime settings. The consuming vHost configuration declares its image and boot inputs.

.. _topo-vhost-x86-rocm:

vhost-x86-rocm
~~~~~~~~~~~~~~

- Inherits ``vhost-x86`` and selects ``ubuntu/24.04/x86_64/rocm/7.0`` through ``image``.
- Configures a virtio root disk and kernel arguments for the serial console, root filesystem and ``modprobe.blacklist=amdgpu``.
- ``single-gpu``, ``gpu-8`` and ``mixed-models`` use this profile to boot the ROCm guest.
- The recipe defines software installation and results; this profile defines simulation-session boot settings.

.. _topo-vhost-arm:

vhost-arm
~~~~~~~~~

- ``virt,gic-version=3``, ``kvm``, ``host`` CPU, 8 GiB RAM, 4 vCPU; binary ``build/qemu/qemu-system-aarch64``.
- ``memory_map`` places RAM at 1 GiB.
- No sample uses this KVM profile directly; it is only the base template of ``vhost-arm-tcg``.

.. _topo-vhost-riscv:

vhost-riscv
~~~~~~~~~~~

- ``virt,aia=aplic-imsic``, ``tcg``, ``rva23s64,sv48=on`` CPU, 4 GiB RAM,
  2 vCPU; binary ``build/qemu/qemu-system-riscv64``.
- ``memory_map`` places RAM at 2 GiB (``0x80000000``); its shared-pool offset
  starts at zero. Device backends receive the guest physical address ranges.

.. _topo-vhost-x86-tcg:

vhost-x86-tcg
~~~~~~~~~~~~~

- Inherits ``vhost-x86`` and overrides it with ``tcg``, ``qemu64``, 64 MiB RAM and 1 vCPU.
- The binary is the bare name ``qemu-system-x86_64``, looked up in ``PATH`` during planning.
- ``args`` is ``[-S, -nodefaults]``, so the vHost stays paused; used for sessions that do not boot an OS.

.. _topo-vhost-arm-tcg:

vhost-arm-tcg
~~~~~~~~~~~~~

- Inherits ``vhost-arm`` and overrides it with ``tcg``, ``cortex-a72``, 64 MiB RAM and 1 vCPU.
- The binary is the bare name ``qemu-system-aarch64``; ``args`` is ``[-S, -nodefaults]``.
- The AArch64 samples and architecture-dependent session tests use this profile.

QEMU command contract
---------------------

The vHost kind renders QEMU arguments from a command template whose context
includes ``vhost``, ``machine``, ``pool``, ``ram``, ``guest_ranges``,
``boot``, ``disks``, ``devices``, ``qmp``, ``serial``, ``serial_log``,
``cmdline``, ``run_dir`` and ``node_dir``.

- ``-machine <machine>,memory-backend=ram``, ``-accel``, ``-m`` and ``-smp``;
- ``memory-backend-file`` (``share=on``, offset at the guest RAM offset) binding the pool;
- a QMP Unix socket; a serial chardev with a logfile;
- optional ``-cpu``, ``-display``, ``-monitor`` and ``-append``; ``-kernel`` and ``-initrd`` when the vHost has ``kernel``; ``-no-reboot`` when ``no_reboot`` is set;
- one ``pcie-root-port`` and one ``vfio-user-pci`` client per device (with ``romfile`` when ``pci.rom`` is set);
- ``virtio-scsi-pci`` when a SCSI disk exists; disks first become ``-blockdev`` file and format nodes, then map to ``virtio-blk-pci``, ``nvme``, ``scsi-hd`` or ``ide-hd`` by ``bus``, with ``bootindex=1`` on the boot disk;
- ``vhost.args`` appended last.

Readiness probes run in order: the serial socket exists, QMP negotiation succeeds, and the optional ``serial.wait_for`` log marker appears. Undefined template values are errors rather than empty strings.

Memory map
----------

- ``memory_map`` is a MiniJinja template that receives ``vhost`` and
  ``ram.size`` and renders 1 to 64 ordered, non-overlapping ranges.
- A machine with a gem5 MI300X device must provide ``memory_map``; machines with QEMU devices only do not need it.
- QEMU maps guest RAM through ``memory-backend-file``; gem5 receives ``--host-memory-ranges`` and ``--shared-pool`` and maps the same pool file. The address space is described in :ref:`arch-memory-model`.

Serial and readiness deadline
-----------------------------

- ``serial.wait_for`` adds a serial readiness marker; ``serial.timeout`` limits that marker in seconds, measured from vHost start, and requires ``wait_for``.
- Without ``serial.timeout`` the session ``--ready-timeout`` applies (default 120 seconds).
- A vHost exiting with status 0 ends its machine; any other exit, a failed probe or cancellation ends the whole session.

Related pages
-------------

- Machine catalog: :doc:`../machines/index`
- Device catalog: :doc:`../devices/index`
- Writing topologies: :doc:`../write_topology`
- Reference: :ref:`ref-topology-schema`
- Chapter 4: :ref:`sim-qemu-vhost`
- Lifecycle: :ref:`launcher-session-lifecycle`
- Sources: ``resources/vhosts/qemu.yaml``, ``resources/vhosts/vhost-x86-tcg.yaml``, ``resources/vhosts/vhost-arm-tcg.yaml``

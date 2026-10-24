.. SPDX-License-Identifier: Apache-2.0

.. _sim-qemu-vhost:

QEMU as vhost
==============

This page describes how the QEMU vHost is launched: machine type and accelerator, memory pool mapping, PCIe topology, direct kernel boot, QMP and serial, and how disks are attached. The command is rendered from a YAML vHost template, so fields and defaults belong to the vHost profiles in chapter 5 and the schema in chapter 6.

Launch Configuration
---------------------

A vHost declares its adapter ``kind``, ``runtime.binary`` and ``runtime.env``, ``memory``, ``cpus``, ``accel`` and ``machine``. Optional fields are ``cpu``, ``display``, ``monitor``, ``no_reboot``, ``memory_align``, ``memory_map``, ``serial`` and ``args``. The ``qemu-vhost`` kind declared in ``resources/vhosts/qemu.yaml`` renders these fields into QEMU arguments.

.. list-table::
   :header-rows: 1

   * - vHost profile
     - Machine and accelerator
     - Purpose
   * - ``vhost-x86``
     - ``q35``, ``accel: kvm``, ``cpu: host``
     - x86_64 guests with 8 GiB RAM and 4 vCPUs by default.
   * - ``vhost-arm``
     - ``virt,gic-version=3``, ``accel: kvm``
     - ARM64 guests with RAM at ``0x40000000``.
   * - ``vhost-x86-tcg``
     - ``q35``, ``accel: tcg``, ``-S``
     - vHost-only and device-model samples with a paused 64 MiB vHost.
   * - ``vhost-arm-tcg``
     - ``virt``, ``accel: tcg``, ``-S``
     - ARM64 device-model samples.

Memory and PCIe Topology
-------------------------

- Guest RAM is mapped from the pool through ``memory-backend-file``: ``mem-path`` points at the machine pool file, ``offset`` is the guest RAM region offset, and ``share=on`` lets gem5 share the same bytes.
- ``memory_map`` describes the guest physical ranges. Q35 splits RAM below and above 4 GiB when memory is large; AArch64 virt starts at 1 GiB. PCI address holes consume no pool bytes.
- Each device receives a dedicated ``pcie-root-port`` at slots ``0x10`` to ``0x17`` with eight functions per port; the vHost kind declares ``max_devices: 64``.
- A device attaches as a ``vfio-user-pci`` client on its root port, with ``socket`` pointing at the device server Unix socket. When ``pci.rom`` is declared, it is passed as the client ``romfile``.
- Disks use the remaining slots, which QEMU assigns itself.

Boot, QMP and Serial
---------------------

- ``kernel`` in the vHost enables direct kernel boot: the launcher emits ``-kernel`` with an optional ``-initrd``, and ``-append`` joins the vHost ``cmdline`` with device ``guest_hints.cmdline`` values.
- The default vHost profiles set ``no_reboot`` so an OS reboot does not hide the end of the session; ``display`` and ``monitor`` are disabled by default.
- The QMP socket is created with ``server=on,wait=off``; the launcher negotiates QMP capabilities after start as one of the vHost readiness probes.
- The serial console is provided through a ``chardev`` socket and written to ``serial.log``. ``serial.wait_for`` makes the launcher wait for a marker in guest output, and ``serial.timeout`` gives that marker a deadline in seconds.
- vHost and device programs must stay in the foreground. ``-daemonize`` is rejected by the launcher because it conflicts with process-group ownership.

.. code-block:: text

   -machine q35,memory-backend=ram
   -accel kvm -m <ram.size>B -smp <cpus> -cpu host
   -object {"qom-type":"memory-backend-file","id":"ram","size":<ram.size>,
            "mem-path":"<pool>","offset":<ram.offset>,"share":true}
   -qmp unix:<run-dir>/m0/qmp.sock,server=on,wait=off
   -chardev socket,id=serial0,path=<run-dir>/m0/serial.sock,server=on,wait=off,logfile=<serial.log>
   -serial chardev:serial0
   -device pcie-root-port,id=rp0,bus=pcie.0,...
   -device vfio-user-pci,bus=rp0,socket={"type":"unix","path":"<device.sock>"}

Disks
------

.. list-table::
   :header-rows: 1

   * - ``bus``
     - QEMU device
     - Notes
   * - ``virtio``
     - ``virtio-blk-pci``
     - Default bus, suitable for the root filesystem.
   * - ``nvme``
     - ``nvme``
     - The serial is derived from the machine and disk identifiers.
   * - ``scsi``
     - ``virtio-scsi-pci`` plus ``scsi-hd``
     - A SCSI controller is appended when needed.
   * - ``ide``
     - ``ide-hd``
     - Compatibility with older images.

Every disk is opened as a file node with ``-blockdev`` and then wrapped in a ``format`` node (``raw`` or ``qcow2``). The ``read-only`` flag comes from the disk declaration, and a disk with ``boot: true`` in the vHost receives ``bootindex=1``.

Sources
--------

- vHost kind and command template: ``resources/vhosts/qemu.yaml``.
- TCG profiles: ``resources/vhosts/vhost-x86-tcg.yaml`` and ``resources/vhosts/vhost-arm-tcg.yaml``.
- vHost argument rendering and probes: ``crates/cosim-topology/src/adapter/mod.rs``.
- Boot vHost: ``resources/vhosts/qemu.yaml``.

Related Pages
--------------

- :doc:`index` for the two QEMU roles.
- :doc:`device_models` for QEMU as a device model.
- :ref:`topo-vhosts` for vHost profile fields and policy.
- :ref:`arch-memory-model` for pools and the shared memory model.
- :ref:`gs-first-session` for the complete first-session commands.

.. SPDX-License-Identifier: Apache-2.0

.. _glossary:

Glossary
========

This page defines the terminology used across the documentation and the code.
Conceptual explanations are in :ref:`arch-index` and field definitions in
:ref:`ref-topology-schema`.

Topology and runtime
--------------------

Topology
  A YAML document describing several machines, with the ``version``,
  ``imports``, ``templates``, ``kinds`` and ``machines`` fields. It
  describes vHosts, their attached devices and how they are started.

Machine
  A runtime unit made of one ``vhost``, all ``device`` processes attached to
  it, and one shared-memory pool. The ``machines`` list expands through
  ``count`` into concrete instances such as ``m0`` to ``m3``.

vHost
  The QEMU process within a machine. Its topology mapping owns CPU, memory,
  image or direct-boot fields and disks, and it acts as the vfio-user client
  for attached devices. Linux running inside QEMU may be called the guest OS;
  ``guest`` is not a separate topology object or configuration layer.

Device
  A natively running process that provides a PCI device to its machine's vHost
  over vfio-user. Devices start through the ``gem5-mi300x`` or
  ``qemu-device`` adapter; the MI300X adapter runs one GPU per process.

Session
  The resource tree created by ``cosim run``: run directory, shared-memory pool
  directory, all processes, locks, disk overlays and logs. A session is prepared
  under a temporary name, published once, and writes a verdict when it ends.

Plan
  The complete execution description printed by ``cosim run --dry-run``: programs,
  arguments, environment, dependencies, readiness probes, memory regions, disk
  targets and lock file paths. ``cosim run`` consumes the plan directly.

Pool
  The per-machine shared-memory file. Guest memory sits at the start and device
  regions follow in declaration order. QEMU maps guest memory through
  ``memory-backend-file``; gem5 maps the same file and locates the VRAM
  regions inside it.

Overlay
  The per-machine qcow2 disk layer created in the session directory. Read-only or
  shared images are written through an overlay, which is removed with the other
  session resources when the session ends.

Verdict
  The result record written to ``verdict.json`` when a session ends, including
  process statuses and ``users_stopped``; the final
  ``[COSIM_VERDICT]`` line repeats its content.

Interfaces and hardware
-----------------------

vfio-user
  A protocol that exports PCI devices over a Unix socket. The vHost side is used by
  QEMU's ``vfio-user-pci`` client; the device side is served by libvfio-user
  (gem5's ``MI300XVfioUser``) or QEMU's ``x-vfio-user-server``.

BAR
  PCI Base Address Register. The MI300X layout maps VRAM on BAR0 and BAR1, a
  2 MiB doorbell on BAR2 and BAR3, 256 MSI-X vectors (an 8 KiB table) on BAR4, and
  512 KiB of MMIO registers on BAR5.

MSI-X
  The PCI interrupt mechanism. A device signals an IRQ eventfd to the vHost, which
  then injects the interrupt into the guest.

DMA mapping
  The vfio-user DMA_MAP operation, which carries a file descriptor and file offset
  so a device can access guest memory. QEMU and the device process exchange data
  through the same shared-memory file.

GART
  Graphics Address Remapping Table, the single-level GPU page table used by VMID
  0. Each page-table entry is eight bytes; in co-simulation the table lives in
  shared VRAM, and gem5 reads entries directly from shared VRAM when its hash
  table misses.

PM4
  AMD's GPU command processor interface. The guest driver writes PM4 commands to a
  queue, and gem5's ``PM4PacketProcessor`` decodes and executes them.

SDMA
  The System DMA engine, responsible for memory copies and part of command
  processing. gem5's ``SDMAEngine`` models its behavior.

IH
  Interrupt Handler. A device writes interrupt records into shared memory, updates
  the write pointer, and then signals the vHost through an IRQ eventfd.

gfx942
  The GPU architecture identifier of the MI300X. ``rocminfo`` reports the agent
  under this name, and HIP compiles with ``--offload-arch=gfx942``.

Simulation and build
--------------------

gem5
  The performance simulator. The MI300X model runs PM4, SDMA, Shader/CU and Ruby
  memory-hierarchy components and exposes the GPU to the QEMU guest over
  vfio-user.

QEMU
  The functional simulation and virtualization component. As a vHost it runs the
  guest Linux; as a device model it provides PCI devices through ``x-remote``
  and ``x-vfio-user-server``.

StubWorkload
  The workload used by the co-simulation gem5 configuration so the device model
  runs without a full CPU workload.

SST
  The Structural Simulation Toolkit. ``configs/sst/`` holds multi-node network
  and MI300X integration experiment configurations and is an independent
  experimental path.

XGMI
  The GPU-to-GPU interconnect. gem5's ``XGMIBridge`` and related configuration
  implement in-simulator interconnect behavior; the YAML adapter runs one GPU per
  process.

Cluster
  A topology combination of several machines. Samples under ``resources/clusters/``
  expand machine counts through ``count``; a cluster is a topology combination,
  not a single machine in the machine catalog.

Adapter
  The abstraction for how a device starts, represented by an adapter enum
  (``gem5-mi300x``, ``qemu-device`` or a custom kind). An adapter defines the
  command, the readiness probe and the number of attachable devices.

Related pages
-------------

- :ref:`arch-index`
- :ref:`ref-topology-schema`
- :ref:`topo-index`

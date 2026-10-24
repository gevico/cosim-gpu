.. SPDX-License-Identifier: Apache-2.0

.. _arch-components:

Components and responsibilities
===============================

The system consists of the Rust launcher, host QEMU, device-model processes
(gem5 or QEMU), the vfio-user link and shared memory pools. This page
describes each part and its boundary.

Overview
--------

.. mermaid::

   flowchart LR
       Y[Topology YAML] --> L[cosim launcher]
       L --> H[Host QEMU]
       L --> G[gem5 MI300X device]
       L --> Q[QEMU device]
       H <-->|vfio-user| G
       H <-->|vfio-user| Q
       H --- P[Machine memory pool]
       G --- P
       Q --- P
       H --> Guest[Linux guest and ROCm]

The launcher reads the topology and vHost, produces an execution plan and
supervises the processes. Simulators run only with the paths, arguments and
memory regions the plan provides.

Component responsibilities
--------------------------

.. list-table::
   :header-rows: 1

   * - Component
     - Process or library
     - Responsibility
   * - ``cosim`` launcher
     - user process
     - Load, validate, plan, run and clean sessions; no simulation work
   * - ``cosim-topology``
     - Rust library
     - YAML parsing and validation, templates, memory layout, argument rendering
   * - ``cosim-runtime``
     - Rust library
     - Plans, session resources, readiness probes, leases, verdict and cleanup
   * - Host QEMU
     - host process
     - Guest CPU, memory and PCIe, QMP and serial; functional simulation
   * - gem5 MI300X
     - device process
     - MI300X performance model as a vfio-user server; performance simulation
   * - QEMU device process
     - device process
     - Exports a PCI device with ``x-vfio-user-server``; functional simulation
   * - vfio-user
     - Unix socket protocol
     - The bridge between host QEMU and the device models
   * - Shared memory pool
     - file
     - Guest memory and device regions mapped by QEMU and the device models

QEMU: functional simulation
---------------------------

QEMU plays two roles here, both functional simulations with no
microarchitectural timing:

- **vhost**: host QEMU runs guest Linux on Q35 or virt with KVM or TCG,
  performs PCIe enumeration, loads the amdgpu driver and provides QMP and a
  serial port for control and observation.
- **device model**: a device QEMU process uses ``-machine x-remote`` and
  ``-object x-vfio-user-server`` to export PCI devices such as ``edu`` as
  vfio-user servers. The model keeps registers and interrupts correct but
  does not model timing.

QEMU does not model GPU performance; gem5 provides MI300X timing. Both kinds
of device can be combined in one machine, as the ``mixed-models`` machine
does.

gem5: performance simulation
----------------------------

gem5 runs the MI300X device model and exposes configuration space, BARs, DMA
mappings and interrupts through ``MI300XVfioUser``. The model covers:

- PM4 command processors and SDMA engines;
- Shader and compute units plus the Ruby memory hierarchy;
- the interrupt handler and GPU address translation (GART, MMHUB and user
  contexts);
- the data path for command queues, completion markers and DMA.

The co-simulation configuration uses ``StubWorkload`` and executes only the
device model. The YAML adapter starts one GPU per gem5 process; the in-process
multi-GPU mode supported by the gem5 configuration is not used by the YAML
path.

vfio-user: the bridge between them
----------------------------------

Host QEMU uses its built-in ``vfio-user-pci`` client, while the device side
is served by gem5's ``MI300XVfioUser`` (libvfio-user) or QEMU's
``x-vfio-user-server``. The protocol runs over a Unix socket and carries PCI
configuration space, MMIO, DMA mappings and interrupts. Details are in
:doc:`vfio_user`.

Supporting infrastructure
-------------------------

- **Shared memory pool**: one file per machine, guest RAM first and device
  regions appended with alignment; the layout is written to ``layout.json``,
  see :doc:`memory_model`.
- **Disks**: the vHost declares the kernel and disks; the session creates
  an overlay per machine or uses the given image.
- **Process supervision**: each process runs in its own process group,
  devices start before the host and stop after it; details in
  :doc:`execution_flow`.
- **Logs and verdict**: the run directory keeps plans, manifests, process
  logs and ``verdict.json``, and the last line is ``[COSIM_VERDICT]``.

Source entry points
-------------------

.. list-table::
   :header-rows: 1

   * - Path
     - Content
   * - ``crates/cosim-topology/src/``
     - YAML types, validation, layout and adapters
   * - ``crates/cosim-runtime/src/``
     - Plans, sessions, probes, resources and cleanup
   * - ``third_party/gem5/configs/example/gpufs/mi300_cosim.py``
     - MI300X objects, pool and vfio-user arguments
   * - ``third_party/gem5/src/dev/amdgpu/``
     - PM4, SDMA, interrupts, GPU VM and the vfio-user server
   * - ``third_party/qemu/hw/remote/vfio-user-obj.c``
     - QEMU device-server interface
   * - ``resources/``
     - Image recipes and sibling directories for vHost, device, machine and cluster configurations

Related pages
-------------

- :doc:`execution_flow`
- :doc:`memory_model`
- :doc:`vfio_user`
- :ref:`QEMU and gem5: functional and performance simulation <sim-index>`
- :ref:`MI300X performance model <sim-gem5-model>`

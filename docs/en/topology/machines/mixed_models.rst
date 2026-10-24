.. SPDX-License-Identifier: Apache-2.0


.. _topo-machines-mixed-models:

mixed-models machine
====================

Overview
--------

``mixed-models`` uses two device adapters in one machine: two gem5 MI300X performance models and two QEMU ``edu`` functional devices exported over vfio-user, sharing a 40 GiB memory pool. It shows that one machine can combine PCI devices from different sources.

Topology
--------

.. code-block:: yaml

   # resources/machines/mixed-models.yaml
   version: 1
   imports:
     - vhosts/qemu.yaml
     - devices/gpu/mi300x.yaml
     - devices/pci/qemu-edu.yaml
   machines:
     - id: m0
       vhost: {use: vhost-x86}
       devices:
         - {use: mi300x, count: 2}
         - {use: qemu-edu, count: 2}

- Machine count: one (``m0``); the host uses the default ``vhost-x86``.
- Device identifiers: ``mi300x-0``, ``mi300x-1``, ``qemu-edu-0``, ``qemu-edu-1``.
- ``qemu-edu`` declares no private memory region; the pool accumulates only 2 × 16 GiB of VRAM.

Hardware resources
------------------

.. list-table::
   :header-rows: 1

   * - Resource
     - Value
     - Source
   * - Machine
     - 1 (``m0``)
     - ``resources/machines/mixed-models.yaml``
   * - vHost profile
     - ``vhost-x86``: ``q35``, ``kvm``, 8 GiB RAM, 4 vCPU
     - ``resources/vhosts/qemu.yaml``
   * - gem5 devices
     - 2 × ``mi300x``, 16 GiB VRAM and 40 CU each
     - ``resources/devices/gpu/mi300x.yaml``
   * - QEMU devices
     - 2 × ``qemu-edu`` with ``args.device`` set to ``{driver: edu}``
     - ``resources/devices/pci/qemu-edu.yaml``
   * - Memory pool
     - 40 GiB = 8 GiB RAM + 32 GiB VRAM
     - ``crates/cosim-topology/src/layout.rs``
   * - Region offsets
     - ``mi300x-0.vram`` at 8 GiB; ``mi300x-1.vram`` at 24 GiB
     - Declaration order
   * - Processes
     - 1 host process + 2 gem5 processes + 2 QEMU device processes
     - Session plan

Software stack
--------------

.. list-table::
   :header-rows: 1

   * - Layer
     - Component
     - Description
   * - Guest OS
     - Ubuntu 24.04.2 LTS, kernel 6.8.0-124-generic
     - vHost optional; without a guest only the hardware and process composition are validated
   * - GPU driver
     - ``amdgpu`` with fixed parameters
     - Applies to the gem5 MI300X devices only
   * - Functional device
     - QEMU ``edu``
     - Test PCI device with no matching guest driver
   * - Device models
     - gem5 performance model + QEMU functional model
     - QEMU devices start with ``-machine x-remote`` and ``x-vfio-user-server``
   * - Guest initialization
     - ``cosim-gpu-initialize.service``
     - Handles AMD PCI devices only

Running this machine
--------------------

.. code-block:: bash

   # Validate and preview
   just run-cli validate resources/machines/mixed-models.yaml  --assets
   just run-topology resources/machines/mixed-models.yaml --dry-run
   # Start a session
   just run-topology resources/machines/mixed-models.yaml

- QEMU device processes need the QEMU built by ``just build-qemu`` with vfio-user support.
- The vHost starts only after all four devices are ready and have handed over their leases; on shutdown the vHost stops first and the devices exit afterwards.
- Lifecycle and readiness probes are described in :ref:`launcher-session-lifecycle`.

Verification
------------

- The plan output is one host process and four device processes, a 40 GiB pool and four vfio-user sockets.
- The sample is loaded by the render test; the MI300X model and the vfio-user device path each have separate test jobs.
- This particular sample, which combines both adapters, has no dedicated end-to-end CI job.

Limitations
-----------

- Both adapters have their own tests, but end-to-end guest behavior of this composition is established by local runs.
- ``qemu-edu`` is a test device with no guest driver; the guest only sees an unbound PCI device.
- Running needs Linux glibc and ``setpriv``; booting a guest needs KVM.
- The 40 GiB pool plus four device processes are resource-heavy; check host memory and ``/dev/shm`` capacity before running.

Related pages
-------------

- Device catalog: :doc:`../devices/index`
- vHost profiles: :doc:`../hosts/index`
- vHost: :ref:`ref-topology-schema`
- Machine catalog: :doc:`index`
- Chapter 4: :ref:`sim-gem5-model`, :ref:`sim-qemu-device-models`
- Sources: ``resources/machines/mixed-models.yaml``, ``resources/devices/gpu/mi300x.yaml``, ``resources/devices/pci/qemu-edu.yaml``

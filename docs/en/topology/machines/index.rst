.. SPDX-License-Identifier: Apache-2.0


.. _topo-machines-index:

Machine catalog
===============

A machine (board) fixes one combination: a vHost, a set of devices and a
memory pool derived from both. This page lists the single-machine boards under
``resources/machines/`` only.

Catalog table
-------------

.. list-table::
   :header-rows: 1

   * - Machine
     - vHost profile
     - Devices and pool
     - Notes
   * - :doc:`single-gpu <single_gpu>`
     - ``vhost-x86`` (Q35, KVM), 8 GiB RAM, 4 vCPU
     - 1 × ``mi300x`` 16 GiB VRAM; 24 GiB pool
     - Canonical one-GPU guest board; the quick start example
   * - :doc:`gpu-8 <gpu_8>`
     - ``vhost-x86``, 32 GiB RAM, 16 vCPU
     - 8 × ``mi300x`` 8 GiB VRAM; 96 GiB pool
     - Multi-GPU per machine and pool sizing example
   * - :doc:`mixed-models <mixed_models>`
     - ``vhost-x86``, 8 GiB RAM, 4 vCPU
     - 2 × ``mi300x`` + 2 × ``qemu-edu``; 40 GiB pool
     - gem5 and QEMU device models in one machine
   * - :doc:`host-only <host_only>`
     - ``vhost-x86-tcg`` (paused), 64 MiB RAM, 1 vCPU
     - No devices; 64 MiB pool
     - QEMU, memory and QMP management without a guest
   * - :doc:`qemu-device <qemu_device>`
     - ``vhost-x86-tcg`` (paused), 64 MiB RAM, 1 vCPU
     - 1 × ``qemu-edu``; 64 MiB pool
     - vfio-user device path and option ROM
   * - :doc:`aarch64 <aarch64>` (host-only-aarch64)
     - ``vhost-arm-tcg`` (paused), 64 MiB RAM, 1 vCPU
     - No devices; 64 MiB pool
     - AArch64 host plumbing
   * - :doc:`aarch64 <aarch64>` (gem5-aarch64)
     - ``vhost-arm-tcg``, 512 MiB RAM, 1 vCPU
     - 1 × ``mi300x-aarch64`` 1 GiB VRAM; 1.5 GiB pool
     - Native ARM64 gem5 build; no AArch64 guest image
   * - :doc:`aarch64 <aarch64>` (qemu-device-aarch64)
     - ``vhost-arm-tcg`` (paused), 64 MiB RAM, 1 vCPU
     - 1 × ``qemu-edu-aarch64``; 64 MiB pool
     - Depends on an AArch64 QEMU build

Machine pages
-------------

.. toctree::
   :maxdepth: 1

   single_gpu
   gpu_8
   mixed_models
   host_only
   qemu_device
   aarch64

How to read a row
-----------------

- vHost profile: defined under ``resources/vhosts/``; profile descriptions are in :doc:`../hosts/index`.
- Devices: models exported over vfio-user; kinds and fields are in :doc:`../devices/index`.
- Devices and pool: the pool size is guest RAM plus device regions; the arithmetic is in :doc:`../single_machine`.
- Notes: facts only, such as the device composition, whether a guest image exists, and which build artifact a board depends on.
- The three AArch64 rows share the series page :doc:`aarch64`.

Recommended reading path
------------------------

- First guest run: :doc:`single_gpu`
- More GPUs: :doc:`gpu_8`
- gem5 and QEMU device models together: :doc:`mixed_models`
- Session lifecycle only: :doc:`host_only`
- vfio-user devices: :doc:`qemu_device`
- AArch64 host plumbing: :doc:`aarch64`

Sources and evidence
--------------------

- Machine samples: ``resources/machines/``.
- Cluster samples (not part of the board layer): ``resources/clusters/``, described in :doc:`../multi_machine`.
- Every sample is loaded by the render test in ``crates/cosim-topology/tests/topology.rs``.

Related pages
-------------

- Topology layer: :doc:`../single_machine`, :doc:`../multi_machine`
- Components: :doc:`../hosts/index`, :doc:`../devices/index`, :ref:`ref-topology-schema`
- Writing topologies: :doc:`../write_topology`

.. SPDX-License-Identifier: Apache-2.0


.. _topo-machines-gpu-8:

gpu-8 machine
=============

Overview
--------

``gpu-8`` is a single-machine, multi-GPU board: one ``vhost-x86`` host with eight gem5 MI300X devices of 8 GiB VRAM each, sharing a 96 GiB memory pool. It shows the process fan-out and pool capacity arithmetic of one machine.

Topology
--------

.. code-block:: yaml

   # resources/machines/gpu-8.yaml
   version: 1
   imports:
     - vhosts/qemu.yaml
     - devices/gpu/mi300x.yaml
   templates:
     node8:
       vhost:
         use: vhost-x86
         memory: 32G
         cpus: 16
       devices:
         - use: mi300x
           count: 8
           memory_regions:
             - {name: vram, size: 8G, align: 2M}
   machines:
     - {id: m0, use: node8}

- Machine count: one (``m0``); the ``node8`` template is also reused by the cluster samples, see :doc:`../multi_machine`.
- ``count: 8`` expands the device identifiers into ``mi300x-0`` through ``mi300x-7``.
- Each device region is 8 GiB aligned to 2 MiB; guest RAM is 32 GiB.

Hardware resources
------------------

.. list-table::
   :header-rows: 1

   * - Resource
     - Value
     - Source
   * - Machine
     - 1 (``m0``)
     - ``resources/machines/gpu-8.yaml``
   * - vHost profile
     - ``vhost-x86``: ``q35``, ``kvm``, 16 vCPU
     - ``resources/vhosts/qemu.yaml``
   * - Guest RAM
     - 32 GiB
     - ``gpu-8.yaml``
   * - Devices
     - 8 × ``mi300x``, 8 GiB VRAM and 40 CU each
     - ``resources/devices/gpu/mi300x.yaml``
   * - Memory pool
     - 96 GiB = 32 GiB RAM + 64 GiB VRAM
     - ``crates/cosim-topology/src/layout.rs``
   * - Region offsets
     - ``mi300x-0.vram`` at 32 GiB; ``mi300x-7.vram`` at 88 GiB
     - Declaration order
   * - Processes
     - 1 host process + 8 gem5 processes
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
     - vHost optional; the board itself describes hardware only
   * - GPU driver
     - ``amdgpu`` with fixed parameters
     - ``ip_block_mask=0x67 ppfeaturemask=0 dpm=0 audio=0 ras_enable=0 discovery=2``
   * - Device model
     - 8 independent gem5 MI300X processes
     - One GPU per process (``--num-gpus=1``)
   * - Guest initialization
     - ``cosim-gpu-initialize.service``
     - Writes the ROM with ``dd`` and runs ``modprobe`` for each simulated device

Running this machine
--------------------

.. code-block:: bash

   # Validate and preview the layout of the 96 GiB pool
   just run-cli validate resources/machines/gpu-8.yaml  --assets
   just run-topology resources/machines/gpu-8.yaml --dry-run
   # Start a session
   just run-topology resources/machines/gpu-8.yaml

- The pool directory needs 96 GiB of free space; on Linux it defaults to a directory under ``/dev/shm``.
- Shutdown follows the single-machine flow: devices stop after the vHost exits; see :ref:`launcher-session-lifecycle`.

Verification
------------

- The plan output contains one host process and eight device processes with a 96 GiB pool; ``layout.json`` records every region offset.
- The sample is loaded by the render test; ``just test-gem5-mi300x`` separately checks the model and the pool.
- No CI job runs the full eight-process guest configuration; multi-GPU guest behavior is established by local runs.

Limitations
-----------

- The 96 GiB pool plus eight gem5 processes are resource-heavy; check memory and ``/dev/shm`` capacity before running.
- The YAML adapter runs one GPU per process; in-process multi-GPU mode of gem5 cannot be enabled from YAML.
- There is no XGMI or inter-GPU fabric model between the eight GPUs; the factual boundary is in :ref:`sim-gem5-multi-gpu`.
- Booting a guest needs KVM; running a session needs Linux glibc and ``setpriv``.

Related pages
-------------

- Single-machine topology and pool arithmetic: :doc:`../single_machine`
- vHost profiles: :doc:`../hosts/index`
- Device catalog: :doc:`../devices/index`
- vHost: :ref:`ref-topology-schema`
- Machine catalog: :doc:`index`
- Chapter 4: :ref:`sim-gem5-model`, :ref:`sim-gem5-multi-gpu`
- Sources: ``resources/machines/gpu-8.yaml``, ``resources/devices/gpu/mi300x.yaml``

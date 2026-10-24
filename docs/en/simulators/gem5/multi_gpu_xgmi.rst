.. SPDX-License-Identifier: Apache-2.0

.. _sim-gem5-multi-gpu:

Multi-GPU and XGMI
===================

This page covers the two ways multiple GPUs exist (the YAML path with one GPU per process and the single-process multi-GPU path), the current XGMI bridge implementation, and the factual boundaries of the SST experiments and the launcher.

Two Run Modes
--------------

.. list-table::
   :header-rows: 1

   * - Mode
     - Entry point
     - Characteristics
   * - One GPU per process
     - The YAML ``gem5-mi300x`` adapter
     - The adapter always passes ``--num-gpus=1`` and ``--shared-pool``; each device process owns its vfio-user socket and VRAM region.
   * - Multiple GPUs in one process
     - Direct ``gem5.opt`` invocation with ``--num-gpus N``
     - Each GPU has its own ``AMDGPUDevice``, Shader and vfio-user bridge; all GPUs share one Ruby cache hierarchy; shared memory uses ``/dev/shm/mi300x-vram-{i}`` names instead of a pool file.

- ``--shared-pool`` and multiple GPUs are mutually exclusive: with ``--shared-pool``, ``--num-gpus`` must be 1.
- To use multiple GPUs on one machine in YAML, declare multiple devices (for example ``count: 8``); the launcher starts one process per GPU. ``resources/machines/gpu-8.yaml`` is such a machine.
- Multiple GPUs in one process exist only in the vfio-user backend; there is no XGMI link between two gem5 processes.

The XGMI Model
---------------

``XGMIBridge`` sits at each GPU L2 (TCC) egress and forwards requests whose target falls in another GPU VRAM range over the modeled xGMI link, using bandwidth throttling, event-based latency and credit-based flow control.

.. list-table::
   :header-rows: 1

   * - Property
     - Default
     - Notes
   * - Link bandwidth
     - ``128GB/s``
     - One direction between a pair of GPUs.
   * - Per-hop latency
     - ``100ns``
     - Modeled with gem5 events.
   * - Lanes
     - ``16``
     - The ``num_lanes`` parameter.
   * - Maximum links
     - ``7``
     - The ``max_links`` parameter.
   * - Flow-control credits
     - ``32``
     - Credits per link; senders are back-pressured when they run out.
   * - Topology
     - ``mesh`` or ``ring``
     - Selected by ``--xgmi-topology`` and requires ``--num-gpus`` of at least 2.

- Packet types are ``WriteReq``, ``ReadReq``, ``ReadResp`` and ``Completion``.
- Remote address detection uses ``vram_size_per_gpu`` to compute each GPU VRAM range.
- ``xgmi_transport.hh`` reserves an abstract transport interface: the in-process implementation uses direct peer pointers. ``IPCTransport`` is a skeleton with TODO markers, and an SST transport belongs to a later design phase; the current configuration does not use it.

Launch Example
---------------

.. code-block:: bash

   # Two GPUs in one process with mesh XGMI (direct gem5 invocation, not YAML)
   build/gem5/x86_64/VEGA_X86/gem5.opt \
     third_party/gem5/configs/example/gpufs/mi300_cosim.py \
     --num-gpus=2 --xgmi-topology=mesh \
     --socket-path=/tmp/gem5-mi300x --shmem-path=/mi300x-vram

In the YAML path, multiple GPUs on one machine are multiple device processes. There is no XGMI model between processes; cross-GPU access follows guest software and the QEMU PCIe topology.

SST Experiments
----------------

- ``configs/sst/multi_node_topology.py`` describes SST network parameters; ``configs/sst/mi300x_merlin_poc.py`` is an SST integration experiment.
- These configurations require the corresponding SST components and have interfaces independent of Rust process management; they are not driven by YAML topologies or ``cosim run``.
- ``placement.agent`` can describe remote placement, but ``cosim run`` rejects remote placement before allocating resources, and switch nodes are not part of the topology format yet.
- Cross-machine DMA and machine-to-machine fabric are outside the current launcher model.

Factual Boundaries
-------------------

- The YAML adapter runs one GPU per process; XGMI and single-process multi-GPU exist only on the direct gem5 invocation path.
- Sockets and shared memory in ``--num-gpus`` mode use GPU-numbered suffixes so several instances can run on one host.
- SST and remote placement are independent experiments or reserved design, not executable launcher paths.
- With multiple GPUs the ROM is read through system memory, and the legacy VGA ROM window is decoded only by GPU 0.

Sources
--------

- Multi-GPU configuration: ``third_party/gem5/configs/example/gpufs/mi300_cosim.py``.
- XGMI bridge: ``third_party/gem5/src/dev/amdgpu/xgmi_bridge.{cc,hh}`` and ``XGMIBridge.py``.
- Transport interface: ``third_party/gem5/src/dev/amdgpu/xgmi_transport.hh``.
- SST configurations: ``configs/sst/``.
- Machine sample: ``resources/machines/gpu-8.yaml``.

Related Pages
--------------

- :doc:`index` for the position of gem5.
- :doc:`mi300x_model` for model components and command paths.
- :ref:`appendix-sst-and-placement` for the SST and remote placement appendix.
- :ref:`topo-multi-machine` for multi-machine topologies and cluster samples.
- :ref:`topo-machines-gpu-8` for the 8-GPU machine sample.

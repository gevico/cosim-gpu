.. SPDX-License-Identifier: Apache-2.0

.. _arch-index:

Architecture overview
=====================

This chapter explains which components make up the system, how a session
flows, how memory and vfio-user connect QEMU with the device models, and what
trade-offs those choices make.

What this chapter covers
------------------------

.. toctree::
   :maxdepth: 1

   components
   execution_flow
   memory_model
   vfio_user
   design_decisions

Design goals
------------

- Run a real Linux guest and the ROCm software stack in QEMU, with a usable
  CPU, PCIe enumeration and standard devices;
- model MI300X performance in gem5 so timing and microarchitecture work is
  separate from functional correctness;
- connect the two with the standard vfio-user protocol, without co-simulation
  patches on the QEMU side;
- declare machines and devices in YAML, with plans that can be previewed,
  supervised and cleaned up;
- share guest memory and VRAM through memory-mapped files instead of copying
  large buffers.

Recommended path
----------------

- Get the big picture: :doc:`components` then :doc:`execution_flow`
- Follow the data path: :doc:`memory_model` then :doc:`vfio_user`
- Understand the reasons: :doc:`design_decisions`
- Need commands, YAML and model details: chapters 3, 4 and 5

Relation to the other chapters
------------------------------

.. list-table::
   :header-rows: 1

   * - Chapter
     - Content
   * - Getting Started
     - Builds and the first session
   * - This chapter
     - Components, execution flow, memory, protocol and decisions
   * - Cosim Launcher
     - CLI, YAML pipeline, session lifecycle and the Rust workspace
   * - QEMU and gem5
     - QEMU vhost/device model and gem5 MI300X model details
   * - Topology and hardware support
     - Machine catalog, host/device/vHost and writing YAML

Related pages
-------------

- :doc:`components`
- :doc:`execution_flow`
- :doc:`memory_model`
- :doc:`design_decisions`
- :ref:`QEMU and gem5: functional and performance simulation <sim-index>`

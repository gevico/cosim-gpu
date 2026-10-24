.. SPDX-License-Identifier: Apache-2.0

.. _index:

cosim-gpu documentation
=======================

cosim-gpu runs a real Linux guest in QEMU and a performance model of the AMD
MI300X GPU in gem5; the two cooperate through vfio-user and shared memory.
Chinese is the primary language and this English tree is kept in sync.

.. grid:: 1 1 2 2
   :gutter: 2

   .. grid-item-card:: Getting Started
      :link: getting_started/index
      :link-type: doc

      From environment setup and builds to the first co-simulation.

   .. grid-item-card:: Architecture
      :link: architecture/index
      :link-type: doc

      Components, execution flow, memory model and the vfio-user interface.

   .. grid-item-card:: Cosim Launcher
      :link: launcher/index
      :link-type: doc

      CLI, YAML pipeline, session lifecycle and extension points of the Rust launcher.

   .. grid-item-card:: QEMU and gem5
      :link: simulators/index
      :link-type: doc

      QEMU as vhost and functional device model; gem5 as the performance simulator.

   .. grid-item-card:: Topology and hardware support
      :link: topology/index
      :link-type: doc

      Single/multi-machine topologies, the machine catalog, hosts and devices.

   .. grid-item-card:: Reference and contributing
      :link: reference/index
      :link-type: doc

      Schemas, parameters, versions and known issues; contribution workflow.

.. toctree::
   :hidden:
   :maxdepth: 1

   getting_started/index
   architecture/index
   launcher/index
   simulators/index
   topology/index
   reference/index
   contributing/index
   glossary
   appendix/sst_and_placement

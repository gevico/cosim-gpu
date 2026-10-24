.. SPDX-License-Identifier: Apache-2.0


.. _topo-multi-machine:

Multi-machine topologies
========================

A multi-machine topology is a document whose ``machines`` list holds several machine entries, or one entry expanded with ``count``. It is still "several independent single machines": each machine has its own host, device processes, memory pool, run subdirectory and disk overlays, and machines have no network or interconnect model between them.

Multi-machine semantics
-----------------------

- Each machine independently selects its vHost, image, device list and pool size.
- Machines do not wait for each other: a host exiting with status 0 ends only its own machine, and the other machines keep running.
- There is no NIC, switch, XGMI or cross-machine DMA model between machines; multi-node network data models live in the separate SST experiments, see :ref:`appendix-sst-and-placement`.
- ``placement.agent`` is parsed and stored, but ``cosim run`` rejects remote placement before creating any resource.

count expansion
---------------

- ``count`` expands ``id: m, count: 4`` into ``m0`` to ``m3``; a topology holds at most 4096 machines.
- Devices accept ``count`` as well; machine and device identifier rules are in :doc:`write_topology`.
- Cluster files import machine files only; imported documents contribute templates, and only the top-level document contributes runnable machines.
- The samples under ``resources/clusters/`` reuse machine definitions by importing templates from ``resources/machines/``.

Cluster samples
---------------

.. list-table::
   :header-rows: 1

   * - Sample
     - Machines
     - Composition
     - Notes
   * - ``cluster-4x8.yaml``
     - 4 (``m0`` to ``m3``)
     - 32 GiB RAM + 8 × 8 GiB VRAM = 96 GiB pool each
     - 4 KVM hosts and 32 gem5 processes; the example input of ``cosim graph``
   * - ``cluster-placed.yaml``
     - 2
     - Same as ``cluster-4x8`` per machine
     - Declares ``placement.agent``; ``cosim run`` rejects remote placement
   * - ``tcg-pair.yaml``
     - 2 (``m0``, ``m1``)
     - ``vhost-x86-tcg`` each, no devices, 64 MiB pool
     - Paused TCG hosts for multi-machine session lifecycle
   * - ``tcg-pair-aarch64.yaml``
     - 2 (``m0``, ``m1``)
     - ``vhost-arm-tcg`` each, no devices, 64 MiB pool
     - Same topology on AArch64

Per-machine resource routing
----------------------------

.. list-table::
   :header-rows: 1

   * - Resource
     - Scope
     - Location
   * - Memory pool
     - One per machine
     - ``<pool-dir>/<machine>/pool``; on Linux under ``/dev/shm/cosim-<name>-<hash>``
   * - Run directory
     - One subdirectory per machine
     - ``.cosim/<name>/<machine>/`` with ``layout.json``, ``plan.json`` and other metadata
   * - vfio-user socket
     - One per device
     - ``<run>/<machine>/<device>.sock``
   * - Disk overlay
     - One per machine
     - Created in the session directory from the vHost disk declarations
   * - Disk locks
     - Shared by the host
     - ``COSIM_DISK_LOCK_DIR``, default ``~/.cache/cosim-gpu/disk-locks``

Running multiple machines
-------------------------

.. code-block:: bash

   # Inspect the structure without starting processes
   just run-cli graph resources/clusters/cluster-4x8.yaml
   just run-cli validate resources/clusters/cluster-4x8.yaml
   # Start a multi-machine session
   just run-topology resources/clusters/tcg-pair.yaml --run-for 5

- ``cosim graph`` renders each machine as a Mermaid subgraph and draws the vfio-user edges between hosts and devices.
- Estimate resources first: ``cluster-4x8`` needs 4 × 96 GiB pools, 4 QEMU hosts and 32 gem5 processes, and the pool directory needs enough space.
- Run constraints are the same as for one machine: Linux glibc and ``setpriv``, devices start before their host and stop after it; see :ref:`launcher-session-lifecycle`.

Limitations
-----------

- There is no cross-machine fabric, scheduling or peer communication implementation; this page describes "several independent machines in one session".
- The SST configurations describe network topology data models only and are not a multi-machine capability of this launcher; see :ref:`appendix-sst-and-placement`.
- Each machine owns its vHost and may select a different image and disks.

Related pages
-------------

- Single-machine composition: :doc:`single_machine`
- Machine catalog: :doc:`machines/index`
- Session lifecycle: :ref:`launcher-session-lifecycle`
- SST and placement: :ref:`appendix-sst-and-placement`

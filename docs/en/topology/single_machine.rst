.. SPDX-License-Identifier: Apache-2.0


.. _topo-single-machine:

Single-machine topologies
=========================

A single-machine topology declares one machine: a QEMU vHost, the device
processes connected to it, and one shared memory pool.

Composition of a machine
------------------------

.. list-table::
   :header-rows: 1

   * - Part
     - Role
     - YAML representation
   * - Machine
     - One independent host in a session
     - An entry with ``id`` in the ``machines`` list
   * - vHost
     - QEMU that runs the guest; binds the pool and provides QMP, serial and PCIe root ports
     - ``vhost.use`` selects a vHost template; image, boot, memory and CPU fields can be overridden
   * - Devices
     - PCI devices exported to the host over vfio-user
     - ``use`` or ``kind`` entries in ``devices``, plus ``count``
   * - Memory pool
     - One file per machine: guest RAM plus device memory regions
     - Derived from host ``memory`` and device ``memory_regions``; never declared directly

.. mermaid::

   flowchart LR
       Y[Single-machine YAML] --> H[QEMU host]
       H --- P[(Memory pool)]
       D0[Device 0] -->|vfio-user| H
       D1[Device N] -->|vfio-user| H
       D0 --- P
       D1 --- P

Process fan-out
---------------

- A machine has exactly one host process; every device is a separate process, so ``count: 8`` yields eight device processes.
- The gem5 MI300X adapter starts one GPU per process (``--num-gpus=1``); more GPUs means more device entries.
- Devices start before the vHost: a ready device hands a lease to each vHost
  that depends on it, and exits only after its last lease is released.
- There is no waiting between machines; several machines in one document are independent, see :doc:`multi_machine`.

Pool arithmetic
---------------

The pool size equals guest RAM plus all device regions:

.. list-table::
   :header-rows: 1

   * - Topology
     - Guest RAM
     - Device regions
     - Memory pool
   * - ``single-gpu``
     - 8 GiB
     - 16 GiB (``mi300x`` default)
     - 24 GiB
   * - ``gpu-8``
     - 32 GiB
     - 8 × 8 GiB = 64 GiB
     - 96 GiB
   * - ``mixed-models``
     - 8 GiB
     - 2 × 16 GiB = 32 GiB (``qemu-edu`` has no private region)
     - 40 GiB
   * - ``gem5-aarch64``
     - 512 MiB
     - 1 GiB
     - 1.5 GiB

- Guest RAM is the first pool region; device regions follow in declaration order. In ``gpu-8``, ``mi300x-0.vram`` starts at 32 GiB and ``mi300x-7.vram`` at 88 GiB.
- Region sizes accept integers or binary units such as ``32G``. Each size must be a multiple of the execution page size, and ``align`` must be a power of two of at least one page (default 2 MiB).
- Every machine records region offsets and sizes in ``layout.json`` in the session directory, so the layout can be checked while planning.

Run directory and resources
---------------------------

A single machine still receives the complete session resources: one run subdirectory, one pool file and one ``layout.json`` per machine; one vfio-user socket per device, plus QMP and serial sockets for the host. The run directory defaults to a session directory under ``.cosim/``, and on Linux the pool directory defaults to ``/dev/shm/cosim-<name>-<hash>``. See :ref:`launcher-session-lifecycle` for the lifecycle details.

A minimal single-machine example
--------------------------------

.. code-block:: yaml

   version: 1
   imports:
     - vhosts/qemu.yaml
     - devices/gpu/mi300x.yaml
   machines:
     - id: m0
       vhost: {use: vhost-x86}
       devices:
         - {use: mi300x}

``resources/machines/single-gpu.yaml`` reuses the same composition through a template; the full authoring rules are in :doc:`write_topology`.

Sources and evidence
--------------------

- Samples: every machine file under ``resources/machines/``.
- Implementation: ``crates/cosim-topology/src/layout.rs`` (pool layout) and ``crates/cosim-runtime/src/layout.rs`` (session paths).
- Commands: ``cosim validate``, ``cosim run --dry-run`` and ``cosim graph``.

Related pages
-------------

- Writing topologies: :doc:`write_topology`
- Machine catalog: :doc:`machines/index`
- Hosts and devices: :doc:`hosts/index`, :doc:`devices/index`
- Memory model: :ref:`arch-memory-model`

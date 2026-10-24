.. SPDX-License-Identifier: Apache-2.0

.. _arch-memory-model:

Memory and shared memory model
==============================

Each machine owns one memory pool file, with guest memory and device regions
at fixed layout positions. QEMU and the device models map the same file, so
guest memory and VRAM are shared.

Memory pools and regions
------------------------

The launcher computes each machine's layout before starting processes:

- guest memory is the first region and device regions follow in declaration
  order;
- every region size is a multiple of the execution page size, and its start
  alignment is a power of two no smaller than a page, 2 MiB by default;
- each region name, offset and size is written to ``layout.json``;
- the total pool size follows the complete layout: 8 GiB of guest RAM plus
  one 16 GiB VRAM region gives a 24 GiB pool.

.. mermaid::

   flowchart LR
       R[guest_ram region] --- H[Host QEMU]
       R --- G0[gem5 device 0]
       R --- G1[gem5 device 1]
       V0[mi300x-0.vram region] --- G0
       V1[mi300x-1.vram region] --- G1
       V0 ---|BAR0 mapping| H
       V1 ---|BAR0 mapping| H

Guest physical addresses and file offsets
-----------------------------------------

Host templates declare the guest physical RAM ranges in ``memory_map``.
Rust validates their order, page boundaries and total size, assigns packed
file offsets and passes the result to gem5 through
``--host-memory-ranges``.

.. list-table::
   :header-rows: 1

   * - vHost profile and guest range
     - Pool file offset
   * - Q35: ``[0, below_4g)``
     - Starts at 0
   * - Q35: ``[4 GiB, 4 GiB + above_4g)``
     - Starts at ``below_4g``
   * - AArch64 virt: ``[1 GiB, 1 GiB + ram_size)``
     - Starts at 0

The guest PCI hole consumes no pool bytes. VRAM regions start after the
complete guest RAM region, and guest physical addresses and file offsets are
separate fields. The standard x86 profile splits RAM into a low range and a
range above 4 GiB, with at most 2 GiB in the low range when RAM is at least
2.75 GiB.

How QEMU and gem5 share it
--------------------------

- QEMU maps the guest memory region with ``memory-backend-file``,
  ``share=on`` and ``offset=ram.offset``;
- gem5's ``PhysicalMemory`` maps guest memory and device memory at the
  assigned offsets, checks the region size and leaves the external file's
  length unchanged;
- ``MI300XVfioUser`` calls ``vfu_setup_region`` with the same VRAM file
  offset in the pool, so the bytes QEMU reaches through BAR0 are the same
  bytes gem5 uses for device memory;
- QEMU device processes have no private region and get guest memory through
  vfio-user DMA mappings.

VRAM access does not go through vfio-user: it is the shared file's BAR
mapping. vfio-user carries configuration space, MMIO, DMA mappings and
interrupts only.

Capacity reservation and session isolation
------------------------------------------

- The launcher reserves pool capacity before starting any simulator;
  concurrent sessions consume filesystem capacity while preparing, and a
  failed reservation releases that session's resources.
- On Linux the pool directory defaults to ``/dev/shm/cosim-<name>-<hash>``;
  other systems use ``<run-dir>/memory``. The directory is created under a
  temporary name with an ownership marker, then published without replacing
  an existing directory.
- A session deletes its pool files and directory at the end; directories
  published by other sessions with the same name are left alone.
- Before checking that the run and pool directories are not nested, existing
  parts of both paths are resolved through symbolic links first.

Data and consistency
--------------------

Guest memory holds command rings, fences, interrupt records, queue
descriptors and DMA buffers; VRAM holds device allocations, discovery data
and GPU page tables. The shared file only provides storage; access ordering,
cache behavior and synchronization are determined by the device model and
guest software. Address translation details are in
:ref:`GPU address translation <sim-gem5-address-translation>`.

Related pages
-------------

- :doc:`components`
- :doc:`vfio_user`
- :ref:`GPU address translation <sim-gem5-address-translation>`
- :ref:`vHost profiles <topo-vhosts>`
- :ref:`Files, artifacts and source map <ref-files-and-artifacts>`

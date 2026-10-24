.. SPDX-License-Identifier: Apache-2.0

.. _ref-known-issues:

Known issues
============

This page is the single source of truth for symptoms, root causes and fixes. Parameters, formats and paths are not repeated here: driver parameter details link to :doc:`guest_parameters` and GART details link to :doc:`gart_format`.

Quick triage
------------

Locate the smallest check for a symptom first, then read the full entry below.

.. list-table::
   :header-rows: 1

   * - Symptom
     - First check
   * - gem5 process exits immediately
     - read the process log; the standalone shell path uses ``docker logs <container>``
   * - QEMU fails to connect
     - confirm gem5 is ready and the socket exists and is reachable
   * - NULL dereference at ``psp_gpu_reset``
     - check that ``ip_block_mask`` is ``0x67``
   * - Many GART translation not found warnings
     - confirm the latest gem5 build, then check the fallback in :doc:`gart_format`
   * - SDMA ring test returns -110
     - check that ``sdma_delay`` is reduced to ``1000``
   * - hipcc cannot find the ROCm device library
     - check ``/opt/rocm/lib`` and use ``--offload-arch=gfx942``
   * - MMIO reads return zero
     - gem5 is not connected or has crashed
   * - ``insmod`` fails
     - kernel release and DKMS module do not match
   * - ``cosim-gpu-initialize.service`` fails
     - ``journalctl -u cosim-gpu-initialize``
   * - BAR layout probe returns -12
     - check the BAR region descriptors exported by ``MI300XVfioUser``

Issue catalog
-------------

Entry numbers match the historical issue numbers for cross-referencing.

4.1 VGA ROM NULL dereference
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Item
     - Description
   * - Symptom
     - ``modprobe amdgpu`` triggers a kernel NULL pointer dereference at ``amdgpu_atom_parse_data_header+0x1b``; the call chain is ``amdgpu_ras_init`` through ``amdgpu_atomfirmware_mem_ecc_supported`` to ``amdgpu_atom_parse_data_header`` with ``RAX=0``.
   * - Root cause
     - All five BIOS discovery methods fail under cosim. The driver logs ``Unable to locate a BIOS ROM`` and continues, and the RAS initialization path calls the parser even when ``atom_context`` is empty.
   * - Fix
     - Write the ROM before ``modprobe``; the command is in the VGA ROM section of :doc:`guest_parameters`. ``cosim-gpu-initialize.service`` does this automatically.

4.2 PSP / SMU firmware load failure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Item
     - Description
   * - Symptom
     - ``PSP load tmr failed!``, ``hw_init of IP block <psp> failed -22`` or ``Fatal error during GPU init``.
   * - Root cause
     - ``ip_block_mask=0x6f`` enables PSP (discovery order index 3), but cosim does not model PSP hardware.
   * - Fix
     - Use ``ip_block_mask=0x67`` to disable both PSP and SMU; see the IP block mask section of :doc:`guest_parameters`.

4.3 GART table not populated under co-simulation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Item
     - Description
   * - Symptom
     - Many ``GART translation for X not found`` warnings; PM4 reads all-zero memory (opcode 0x0); the KIQ ring test times out.
   * - Root cause
     - VRAM is backed by shared memory and driver writes bypass the gem5 memory system, so ``AMDGPUVM::gartTable`` is never populated through ``writeFrame()``.
   * - Fix
     - The translation path reads PTEs directly from shared VRAM when ``gartTable`` misses; see the fallback lookup in :doc:`gart_format`.

4.4 Crash on unmapped GART pages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Item
     - Description
   * - Symptom
     - gem5 segfaults after ``hipMalloc`` succeeds, with repeated ``GART translation for 0x3fff800000000 not found``; infinite DMA retries exhaust memory.
   * - Root cause
     - The PM4/SDMA engines DMA to GART pages the driver has not mapped (PTE 0). The original code raised ``GenericPageTableFault`` and the DMA callback chain retried the same address forever.
   * - Fix
     - Map unmapped GART pages to a sink (``paddr=0``): reads return zero and writes are discarded. The first page at ``ptStart`` being unmapped is normal.

4.5 SDMA ring test timeout
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Item
     - Description
   * - Symptom
     - The SDMA ring test returns ``-110`` (``-ETIMEDOUT``) during driver initialization: ``sdma v4_4_2: ring 0 test failed (-110)``.
   * - Root cause
     - ``sdma_delay`` defaults to ``1e9`` ticks, about 500 ms under cosim, which exceeds the driver timeout window of about 200 ms.
   * - Fix
     - Reduce ``sdma_delay`` from ``1e9`` to ``1000`` ticks and raise ``KEEPALIVE_INTERVAL`` to ``1e9`` so keepalive traffic does not disturb timing.

4.6 VRAM address GART translation errors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Item
     - Description
   * - Symptom
     - Address ``0x1f72fa8000`` produces more than 861000 GART translation errors, followed by memory exhaustion and a segfault.
   * - Root cause
     - SDMA rptr writebacks and PM4 ``RELEASE_MEM`` destinations may point at VRAM (below 16 GiB); ``getGARTAddr()`` finds no matching page table entry for them.
   * - Fix
     - Three-layer defense: PM4 ``writeData()``, ``releaseMem()`` and ``queryStatus()`` check ``isVRAMAddress()`` and route to the GPU memory manager; SDMA skips ``getGARTAddr()`` for VRAM addresses; the GART fallback maps VRAM addresses to the sink.

4.7 Shared memory file offset mismatch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Item
     - Description
   * - Symptom
     - GART page table entries read back as all zeros and PM4 opcode 0x0 repeats.
   * - Root cause
     - QEMU Q35 fixes ``below_4g`` at 2 GiB for 8 GiB RAM, while the gem5 configuration assumes 3 GiB below and 5 GiB above, so data above 4 GiB lands at a file offset that differs by 1 GiB.
   * - Fix
     - ``mi300_cosim.py`` replicates the Q35 split: ``below_4g = min(total_mem, 0x80000000 if total_mem >= 0xB0000000 else 0xB0000000)``.

4.8 Timer overflow crash
~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Item
     - Description
   * - Symptom
     - After billions of ticks gem5 crashes on ``curTick()`` integer overflow and a ``schedule()`` assertion fails.
   * - Root cause
     - RTC and PIT timers keep scheduling events and exhaust the tick counter in long-running cosim sessions.
   * - Fix
     - Add ``disable_rtc_events`` to ``Cmos`` and ``disable_timer_events`` to ``I8254`` and disable both in ``mi300_cosim.py``; a keepalive event in the cosim bridge keeps the event queue non-empty.

4.9 PM4ReleaseMem.dataSelect panic
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Item
     - Description
   * - Symptom
     - gem5 panics with ``Unimplemented PM4ReleaseMem.dataSelect``.
   * - Root cause
     - ``pm4_packet_processor.cc`` implemented only ``dataSelect == 1`` (32-bit write), while the driver uses other modes during GFX initialization.
   * - Fix
     - Handle the common values: 0 writes no data, 1 is a 32-bit write, 2 is a 64-bit write, 3 is a 64-bit GPU clock counter, and other values warn and are treated as no-ops.

4.10 Unhandled PM4 opcodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Item
     - Description
   * - Symptom
     - gem5 crashes on an unrecognized PM4 opcode.
   * - Root cause
     - ``ACQUIRE_MEM`` (``0x58``) and ``SET_RESOURCES`` (``0xA0``) were not handled.
   * - Fix
     - Both were added to ``pm4_defines.hh`` and are handled as skip-and-continue (NOP) in ``pm4_packet_processor.cc:decodeHeader()``.

4.11 PCI class code mismatch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Item
     - Description
   * - Symptom
     - The amdgpu driver skips the legacy VGA ROM check at ``0xC0000``.
   * - Root cause
     - The PCI class was ``PCI_CLASS_DISPLAY_OTHER`` (``0x0380``) instead of ``PCI_CLASS_DISPLAY_VGA`` (``0x0300``).
   * - Fix
     - Set the device class to ``PCI_CLASS_DISPLAY_VGA`` so the kernel treats the range as a video device with a shadowed ROM.

4.12 QEMU serial console conflict
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Item
     - Description
   * - Symptom
     - The guest produces no serial output when ``-serial unix:...`` and ``-nographic`` are used together.
   * - Root cause
     - ``-nographic`` implies ``-serial mon:stdio`` and creates serial0 on stdio; an explicit ``-serial unix:...`` becomes serial1 (ttyS1), while the kernel uses ``console=ttyS0``.
   * - Fix
     - Use ``-nographic`` alone; run QEMU inside ``screen`` when programmatic access is needed.

4.13 Out of memory while linking gem5
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Item
     - Description
   * - Symptom
     - The linker is killed by the OOM killer even with ``-j2``.
   * - Root cause
     - The default linker uses too much memory.
   * - Fix
     - Use ``just build-gem5 1 GOLD_LINKER=True --linker=gold``.

4.14 DRM client error -13 (missing DKMS module)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Item
     - Description
   * - Symptom
     - Driver initialization reports ``Failed to init DRM client: -13`` followed by a kernel panic in ``ttm_resource_move_to_lru_tail``.
   * - Root cause
     - The disk image lacks the ``amddrm_exec.ko.zst`` DKMS module, so the TTM memory manager fails to initialize and ``drm_dev_enter()`` returns ``-EACCES``.
   * - Fix
     - Rebuild the disk image with ``just build-disk`` and confirm that ``/lib/modules/6.8.0-124-generic/updates/dkms/amddrm_exec.ko.zst`` exists.

4.15 rmmod oops after a driver hw_init failure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Item
     - Description
   * - Symptom
     - After ``hw_init`` fails, ``rmmod amdgpu`` triggers a kernel oops (page fault in ``kgd2kfd_device_exit``) and the module stays busy.
   * - Root cause
     - The cleanup path after partial initialization is not robust enough.
   * - Fix
     - There is no reliable workaround; restart the whole cosim environment: stop QEMU, restart the gem5 process, then start QEMU again.

Sources and maintenance
-----------------------

The records come from cosim debugging and model changes. When a fix lands, update the implementation and the matching entry together:

- Driver parameters and ROM write: :doc:`guest_parameters`.

- GART and address translation: :doc:`gart_format`, :ref:`sim-gem5-address-translation`.

- gem5 model behaviour and debug flags: :ref:`sim-gem5-model`, :ref:`sim-debugging-models`.

- Session logs, verdicts and cleanup: :ref:`launcher-debugging-sessions`.

When reporting a new issue, include the symptom, reproduction command, gem5 version or commit, driver dmesg and the relevant log excerpt, then classify it here.

Related pages
-------------

- Guest parameters: :doc:`guest_parameters`

- GART format: :doc:`gart_format`

- Version matrix: :doc:`version_matrix`

- Files and session directories: :doc:`files_and_artifacts`

- Legacy launcher options: :doc:`legacy_launcher_flags`

- Guest driver requirements: :ref:`sim-guest-driver`

- Model debugging: :ref:`sim-debugging-models`

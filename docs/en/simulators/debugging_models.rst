.. SPDX-License-Identifier: Apache-2.0

.. _sim-debugging-models:

Model debugging
================

This page covers enabling gem5 debug output, where to read logs, and the order in which to investigate common MI300X model problems. The complete issue list is :ref:`ref-known-issues`.

Enabling gem5 Debug Output
---------------------------

.. list-table::
   :header-rows: 1

   * - Debug flag
     - What it shows
   * - ``MI300XCosim``
     - vfio-user messages, listener and interrupt interaction.
   * - ``AMDGPUDevice``
     - MMIO register reads and writes, ROM accesses and IH pointers.
   * - ``PM4PacketProcessor``
     - PM4 packet decoding and processing.
   * - ``SDMAEngine``
     - SDMA operations and completion paths.
   * - ``SDMAData``
     - SDMA packet data details.
   * - ``AMDGPUMem``
     - GPU memory manager allocation and access.
   * - ``AMDGPUSystemHub``
     - SystemHub accesses.
   * - ``XGMIBridge``
     - xGMI routing in in-process multi-GPU mode.

Enable flags through the device ``args.gem5_debug_flags`` in YAML; the adapter renders them as gem5 ``--debug-flags=...``. When invoking gem5 directly, pass ``--debug-flags`` and use ``--debug-file`` to choose the output file. The default output is stdout, so launcher-managed sessions capture it in ``output.log``.

.. code-block:: yaml

   templates:
     mi300x:
       kind: gem5-mi300x
       args:
         gem5_debug_flags: [MI300XCosim, AMDGPUDevice, PM4PacketProcessor]

Log Locations
--------------

.. list-table::
   :header-rows: 1

   * - Location
     - Contents
   * - ``.cosim/<name>/m0/mi300x-0/output.log``
     - gem5 standard output and standard error, including debug output and warnings.
   * - ``.cosim/<name>/m0/mi300x-0/m5out/``
     - gem5 statistics and output directory.
   * - ``.cosim/<name>/m0/vhost/serial.log``
     - Guest serial log for observing driver-side behavior.
   * - ``.cosim/<name>/verdict.json``
     - Session result; read it first to decide which component failed.
   * - ``docker logs`` and ``/tmp/cosim-<run-id>.log``
     - gem5 container and screen logs under the legacy shell launcher.

Common Model Problems
----------------------

.. list-table::
   :header-rows: 1

   * - Symptom
     - First check
     - Action
   * - Many ``GART translation ... not found`` or ``mapped to sink`` messages
     - Shared VRAM offsets, PTE contents and whether the gem5 binary is current
     - Confirm the pool offsets match the memory layout; occasional warnings are normal, but a continuous flood indicates a page-table or offset problem.
   * - ``Unimplemented PM4ReleaseMem.dataSelect`` panic
     - The dataSelect value used by the driver
     - The model implements 0, 1, 2 and 3; other values need an extension in ``pm4_packet_processor.cc``.
   * - Unknown PM4 opcode
     - The opcode number
     - ``ACQUIRE_MEM`` and ``SET_RESOURCES`` are skipped; others need an implementation or a confirmed safe skip.
   * - SDMA ring test returns ``-110``
     - ``sdma_delay`` and the keepalive interval
     - Confirm ``sdma_delay`` is 1000 ticks and nothing else blocks the event queue.
   * - All MMIO reads return zero
     - Whether gem5 connected and whether ``output.log`` shows a crash
     - Check the readiness marker and socket; enable only ``MI300XCosim`` to observe the protocol.
   * - BAR layout probe error ``-12``
     - BAR region descriptions and sizes
     - Check the BAR setup in ``MI300XVfioUser`` and the VRAM size in the memory layout.
   * - Timer overflow crash
     - Whether RTC and PIT events are disabled
     - ``mi300_cosim.py`` disables ``disable_rtc_events`` and ``disable_timer_events`` by default.

Debugging Workflow
-------------------

1. Run ``cosim run --dry-run`` first to confirm the rendered gem5 arguments, socket, pool offsets and VRAM size.
2. Enable one dimension of flags in ``args.gem5_debug_flags``, rerun and inspect ``output.log``.
3. Read ``verdict.json`` to identify the failing process, then narrow down layer by layer: ``MI300XCosim`` for protocol, ``AMDGPUDevice`` for registers, ``PM4PacketProcessor`` and ``SDMAEngine`` for commands.
4. Run ``just test-gem5-mi300x`` for the QEMU-free model self-test that checks pool ownership and the GPU_VIPER protocol.
5. After changing the model, rebuild incrementally with ``just build-gem5 1`` and rerun the session.

Common Commands
----------------

.. code-block:: bash

   # Rerun the session with the development build
   just run-topology-dev resources/machines/single-gpu.yaml
   # Filter protocol, address translation and fatal errors
   grep -E "MI300XCosim|GART|panic|unimplemented" .cosim/<name>/m0/mi300x-0/output.log
   # QEMU-free model self-test (pool ownership and GPU_VIPER)
   just test-gem5-mi300x
   # Incremental gem5 build
   just build-gem5 1

Sources
--------

- Debug flag definitions: ``third_party/gem5/src/dev/amdgpu/SConscript``.
- vfio-user server: ``third_party/gem5/src/dev/amdgpu/mi300x_vfio_user.cc``.
- PM4 and SDMA: ``third_party/gem5/src/dev/amdgpu/pm4_packet_processor.cc`` and ``sdma_engine.cc``.
- Model self-test: ``third_party/gem5/tests/mi300x/verify.py``.
- Debug options: ``--debug-flags``, ``--debug-file`` and ``--outdir`` in ``third_party/gem5/src/python/m5/main.py``.

Related Pages
--------------

- :doc:`gem5/mi300x_model` for model components and command paths.
- :doc:`gem5/address_translation` for the meaning of GART warnings.
- :doc:`guest_driver` for driver-side failures and the ROM order.
- :doc:`../launcher/debugging_sessions` for session-level logs and verdicts.
- :ref:`ref-known-issues` for the complete known-issue list.

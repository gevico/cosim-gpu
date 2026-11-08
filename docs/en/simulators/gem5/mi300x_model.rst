.. SPDX-License-Identifier: Apache-2.0

.. _sim-gem5-model:

MI300X model
=============

This page describes the components, command and interrupt paths, and timing-related implementation choices of the gem5 MI300X model. The PCI interface is in :doc:`mi300x_pci` and address translation is in :doc:`address_translation`.

System Composition
-------------------

.. mermaid::

   flowchart TD
       Q[Host QEMU] -->|vfio-user| V[MI300XVfioUser]
       V --> A[AMDGPUDevice]
       A --> P[PM4PacketProcessor]
       A --> S[SDMAEngine]
       A --> I[InterruptHandler]
       A --> M[AMDGPUVM]
       A --> H[NBIO / SystemHub / SMU]
       P --> G[Shader and CU arrays]
       S --> R[Ruby Disjoint_VIPER]
       G --> R

Arguments Passed by the Launcher
---------------------------------

The ``gem5-mi300x`` adapter passes the following arguments to the configuration script; values come from the memory layout and the device ``args``.

.. list-table::
   :header-rows: 1

   * - Argument
     - Effect
   * - ``--outdir``
     - Places ``m5out`` in the device work directory.
   * - ``--debug-flags``
     - Optional gem5 debug flags from ``args.gem5_debug_flags``.
   * - ``--listener-mode=off``
     - Disables the gem5 interactive listener.
   * - ``--socket-path``
     - The vfio-user Unix socket.
   * - ``--shared-pool``
     - The machine pool file shared by guest RAM and VRAM.
   * - ``--pool-vram-offset``
     - Offset of this GPU VRAM region in the pool.
   * - ``--dgpu-mem-size``
     - VRAM size of this GPU from the memory layout.
   * - ``--mem-size``
     - Guest RAM size.
   * - ``--host-memory-ranges``
     - JSON description of guest physical ranges and pool offsets.
   * - ``--num-compute-units``
     - Compute units per GPU from ``args.num_compute_units``.
   * - ``--num-gpus=1``
     - The YAML adapter starts one GPU per process.

Component Responsibilities
---------------------------

.. list-table::
   :header-rows: 1

   * - Component
     - Source
     - Responsibility
   * - ``MI300XVfioUser``
     - ``mi300x_vfio_user.cc``
     - Configuration space, BARs, DMA mappings and interrupts as a libvfio-user server.
   * - ``AMDGPUDevice``
     - ``amdgpu_device.cc``
     - MMIO decoding, ROM reads, doorbell handling, IP block register dispatch and ``intrPost()``.
   * - ``PM4PacketProcessor``
     - ``pm4_packet_processor.cc``
     - PM4 packet decoding, ``writeData``, ``releaseMem`` and ``queryStatus``; VRAM address routing; unknown opcodes are skipped.
   * - ``SDMAEngine``
     - ``sdma_engine.cc``
     - SDMA packet execution, reads and writes, rptr writeback and VRAM address handling.
   * - ``AMDGPUInterruptHandler``
     - ``interrupt_handler.cc``
     - Writes IH ring records, advances the write pointer and requests interrupts.
   * - ``AMDGPUVM``
     - ``amdgpu_vm.cc``
     - AGP, GART, MMHUB and user-context translation; shared VRAM fallback.
   * - Shader and CU arrays
     - ``third_party/gem5/src/gpu/`` and the configuration script
     - The CU count per GPU comes from ``num_compute_units`` and is wired through the GPUTLB configuration.
   * - Ruby ``Disjoint_VIPER``
     - ``third_party/gem5/configs/example/gpufs/Disjoint_VIPER.py``
     - GPU caches and memory hierarchy, retaining Ruby request handling and cache behavior.

Command and Interrupt Paths
----------------------------

.. mermaid::

   sequenceDiagram
       participant Guest as Guest driver
       participant Host as QEMU host
       participant GPU as gem5 device
       participant RAM as Shared RAM/VRAM
       Guest->>RAM: write ring and descriptors
       Guest->>Host: write doorbell BAR
       Host->>GPU: vfio-user BAR write
       GPU->>RAM: read commands and data
       GPU->>GPU: PM4, SDMA and shader work
       GPU->>RAM: write completion and IH record
       GPU->>Host: notify IRQ eventfd
       Host->>Guest: inject interrupt
       Guest->>RAM: read completion

- PM4 and SDMA choose the device-memory or system-memory path from the address and VM context. System-memory operations use shared guest memory, and device-memory operations use the VRAM region.
- After completion values and IH records are written to shared memory, ``AMDGPUDevice::intrPost()`` reaches the IRQ eventfd through ``MI300XVfioUser``.
- The guest reads IH records and completion values from shared memory and does not depend on private gem5 data structures.

Timing-Related Choices
-----------------------

- The gem5 system uses the ``atomic_noncaching`` memory mode. QEMU executes the guest kernel and gem5 simulates the GPU side only.
- SDMA operations are scheduled with the ``sdma_delay`` constant, currently 1000 ticks, which must fit the driver ring-test timeout window of about 200 ms.
- ``MI300XVfioUser`` schedules a keepalive every 1e9 ticks, which keeps the event queue non-empty and leaves time for SDMA processing.
- ``gem5.py`` disables event scheduling for the CMOS RTC and the 8254 PIT (``disable_rtc_events`` and ``disable_timer_events``) to avoid tick overflow in long runs.
- Timing behavior follows the event scheduling of these components and the Ruby model; changing the CU count, VRAM size or clocks changes it.

Not Modeled
------------

- PSP, SMU/power management, audio and RAS are not modeled. SMU-prefixed registers are handled by ``AMDGPUSmu`` but there is no real power management behavior.
- There is no x86 kernel and no BIOS discovery flow on the gem5 side; the guest must write the VBIOS into shared memory.
- PCIe switches, machine-to-machine fabric and multi-machine interconnects are outside the current model. In-process multi-GPU and XGMI are described in :doc:`multi_gpu_xgmi`.

Sources
--------

- Configuration script: ``resources/devices/gpu/mi300x/gem5.py``.
- Device model directory: ``third_party/gem5/src/dev/amdgpu/``.
- Debug flag definitions: ``third_party/gem5/src/dev/amdgpu/SConscript``.
- Model self-test: ``just test-gem5-mi300x`` runs ``third_party/gem5/tests/mi300x/verify.py``.

Related Pages
--------------

- :doc:`mi300x_pci` for the PCI and BAR interface.
- :doc:`address_translation` for translation and the shared VRAM fallback.
- :doc:`multi_gpu_xgmi` for multi-GPU and XGMI.
- :doc:`../debugging_models` for debug flags and common model problems.
- :ref:`arch-memory-model` for shared memory and address spaces.

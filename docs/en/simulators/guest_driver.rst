.. SPDX-License-Identifier: Apache-2.0

.. _sim-guest-driver:

Guest driver requirements
==========================

This page describes what co-simulation requires from the guest kernel, the amdgpu driver parameters and the ROM write order. The canonical parameter table and its rationale live in :ref:`ref-guest-parameters`; driver internals belong to the kernel source.

Image and Driver Prerequisites
-------------------------------

- The guest image needs an amdgpu DKMS module matching the kernel (ROCm 7.0) together with companion modules such as ``amddrm_exec``; a missing module makes TTM initialization fail.
- The IP discovery firmware lives at ``/usr/lib/firmware/amdgpu/mi300_discovery``, so ``discovery=2`` can read IP information from a file on disk.
- The VBIOS file lives at ``/root/roms/mi300.rom`` and must be written into shared memory before the driver loads.
- Automatic loading is provided by ``/lib/systemd/system/cosim-gpu-initialize.service`` and ``/usr/local/bin/cosim-gpu-initialize.sh``: write the ROM first, then run ``modprobe``.

Kernel Command Line
--------------------

The sample vHost template ``resources/vhosts/qemu.yaml`` uses the following command line:

.. code-block:: text

   console=ttyS0 root=/dev/vda1 rw nokaslr modprobe.blacklist=amdgpu

``modprobe.blacklist=amdgpu`` prevents the PCI subsystem from loading the driver before the ROM is written into shared memory. The vHost template joins the vHost ``cmdline`` with device ``guest_hints.cmdline`` values and passes the result to QEMU ``-append``.

Driver Parameters
------------------

.. code-block:: bash

   modprobe amdgpu ip_block_mask=0x67 ppfeaturemask=0 dpm=0 audio=0 ras_enable=0 discovery=2

- ``ip_block_mask=0x67`` enables only common, GMC, IH, GFX and SDMA and disables PSP and SMU. Using ``0x6f`` enables PSP and makes initialization fail.
- ``ppfeaturemask=0`` and ``dpm=0`` disable PowerPlay and dynamic power management because co-simulation has no power management hardware.
- ``audio=0`` disables HDMI/DP audio because there is no audio hardware.
- ``ras_enable=0`` avoids a NULL dereference when ``atom_context`` is absent with the minimized VBIOS.
- ``discovery=2`` reads IP discovery information from the firmware file instead of the GPU ROM or registers.

ROM Write Order
----------------

Before ``modprobe``, run:

.. code-block:: bash

   dd if=/root/roms/mi300.rom of=/dev/mem bs=1k seek=768 count=128

This writes the 128 KiB MI300X VBIOS to physical addresses ``0xC0000`` to ``0xDFFFF``, which ``AMDGPUDevice::readROM()`` in gem5 reads from shared guest memory. The explicit write is required because all five amdgpu BIOS discovery paths fail in co-simulation:

.. list-table::
   :header-rows: 1

   * - BIOS discovery path
     - Why it fails
   * - ``amdgpu_atrm_get_bios()``
     - QEMU Q35 has no ACPI ATRM method.
   * - ``amdgpu_acpi_vfct_bios()``
     - There is no ACPI VFCT table.
   * - ``amdgpu_read_bios_from_rom()``
     - It reads through SMU registers, but SMU is disabled by ``ip_block_mask=0x67``.
   * - ``amdgpu_read_platform_bios()``
     - No platform ROM is provided.
   * - ``amdgpu_read_disabled_bios()``
     - Not functional under co-simulation.

Automatic Loading and Manual Recovery
--------------------------------------

On a normal boot ``cosim-gpu-initialize.service`` performs the ROM write and the driver load. For manual recovery:

.. code-block:: bash

   dd if=/root/roms/mi300.rom of=/dev/mem bs=1k seek=768 count=128
   modprobe amdgpu ip_block_mask=0x67 ppfeaturemask=0 dpm=0 audio=0 ras_enable=0 discovery=2
   dmesg | grep -i amdgpu | tail -20

Verification
-------------

.. code-block:: bash

   # Is the driver loaded and is gfx942 detected?
   lsmod | grep amdgpu
   dmesg | grep -i -E "amdgpu|gfx942" | tail -30
   # IP discovery and queue state
   rocminfo | head -40
   rocm-smi
   # Did the automatic setup service succeed?
   systemctl status cosim-gpu-initialize.service

Seeing the MI300X device, the ``gfx942`` agent and usable ROCm queues means the functional path works. The first HIP program is covered in :ref:`gs-verify-guest`.

Common Failures
----------------

.. list-table::
   :header-rows: 1

   * - Symptom
     - First check
     - Action
   * - NULL dereference during ``modprobe``
     - Whether the ROM was written and ``ras_enable=0`` is set
     - Run the ROM write, then ``modprobe`` in that order.
   * - ``PSP load tmr failed``
     - ``ip_block_mask``
     - Use ``0x67`` rather than ``0x6f``.
   * - ``Failed to init DRM client: -13``
     - Whether ``amddrm_exec.ko.zst`` is present in the image
     - Rebuild the image with ``just build-disk``.
   * - ``insmod`` reports a kernel version mismatch
     - The DKMS modules and ``uname -r``
     - Rebuild or replace the image with a matching kernel.
   * - ``cosim-gpu-initialize.service`` fails
     - ``journalctl -u cosim-gpu-initialize``
     - Fix according to the log, then run the manual commands.

Sources
--------

- Automatic initialization script: ``resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/files/cosim_gpu_initialize.sh``.
- Boot vHost: ``resources/vhosts/qemu.yaml``.
- Driver-side ROM read: ``readROM()`` in ``third_party/gem5/src/dev/amdgpu/amdgpu_device.cc``.
- Canonical parameter reference: :ref:`ref-guest-parameters`.

Related Pages
--------------

- :doc:`qemu/vhost` for how the guest boots.
- :doc:`gem5/mi300x_pci` for the ROM BAR and the VGA ROM window.
- :doc:`debugging_models` for model-side debugging after driver load.
- :ref:`ref-guest-parameters` for modprobe, dd and IP mask references.
- :ref:`ref-known-issues` for the complete known-issue list.
- :ref:`gs-verify-guest` for verifying the guest and the first HIP program.

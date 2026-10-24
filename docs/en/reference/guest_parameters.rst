.. SPDX-License-Identifier: Apache-2.0

.. _ref-guest-parameters:

Guest parameters
================

This page is the single source of truth for cosim guest driver parameters: the amdgpu module parameters, the VGA ROM write, the kernel command line and the IP block mask are defined here. Other chapters explain when to run these steps and link back.

amdgpu modprobe parameters
--------------------------

All six parameters are required. The full command is:

.. code-block:: bash

   modprobe amdgpu ip_block_mask=0x67 ppfeaturemask=0 dpm=0 audio=0 ras_enable=0 discovery=2

.. list-table::
   :header-rows: 1

   * - Parameter
     - Value
     - Required
     - Purpose
   * - ``ip_block_mask``
     - ``0x67``
     - yes
     - enables common, GMC, IH, GFX and SDMA, disables PSP (bit 3) and SMU (bit 4); see the mask section below
   * - ``ppfeaturemask``
     - ``0``
     - yes
     - disables every PowerPlay feature; cosim has no power-management hardware
   * - ``dpm``
     - ``0``
     - yes
     - disables dynamic power management
   * - ``audio``
     - ``0``
     - yes
     - disables HDMI/DP audio; cosim has no audio hardware
   * - ``ras_enable``
     - ``0``
     - yes
     - disables RAS and avoids a crash when the minimal VBIOS (about 3 KB) leaves ``atom_context`` empty
   * - ``discovery``
     - ``2``
     - yes
     - reads IP discovery from a firmware file on disk instead of the GPU ROM or registers

.. warning::

   ``ip_block_mask=0x6f`` enables PSP firmware loading and panics the kernel; cosim uses ``0x67``.

.. warning::

   ``ras_enable=0`` is mandatory. Without it, ``amdgpu_ras_init`` calls ``amdgpu_atom_parse_data_header`` on an empty ``atom_context`` and crashes with a NULL pointer dereference.

VGA ROM write
-------------

Before ``modprobe``, write the VBIOS to guest physical address ``0xC0000``:

.. code-block:: bash

   dd if=/root/roms/mi300.rom of=/dev/mem bs=1k seek=768 count=128

.. list-table::
   :header-rows: 1

   * - Parameter
     - Value
     - Meaning
   * - ``if``
     - ``/root/roms/mi300.rom``
     - ROM file inside the guest image
   * - ``of``
     - ``/dev/mem``
     - physical memory device
   * - ``bs``
     - ``1k``
     - block size of 1024 bytes
   * - ``seek``
     - ``768``
     - seek to 768 times 1024, that is physical address ``0xC0000``
   * - ``count``
     - ``128``
     - write 128 times 1024, that is 128 KiB

The range is ``0xC0000`` to ``0xDFFFF`` inside shared guest memory. gem5 reads it in ``AMDGPUDevice::readROM()`` through ``system->getPhysMem()``, so the write must happen before ``modprobe``. All five amdgpu BIOS discovery methods fail under cosim:

.. list-table::
   :header-rows: 1

   * - BIOS discovery method
     - Why it fails under cosim
   * - ``amdgpu_atrm_get_bios()``
     - QEMU Q35 has no ACPI ATRM method
   * - ``amdgpu_acpi_vfct_bios()``
     - no ACPI VFCT table
   * - ``amdgpu_read_bios_from_rom()``
     - reads through SMU registers, but SMU is disabled by ``0x67``
   * - ``amdgpu_read_platform_bios()``
     - no platform-provided ROM
   * - ``amdgpu_read_disabled_bios()``
     - not functional under cosim

Kernel command line
-------------------

The guest kernel boots with the following command line, recorded in the vHost ``cmdline``:

.. code-block:: text

   console=ttyS0 root=/dev/vda1 rw nokaslr modprobe.blacklist=amdgpu

.. list-table::
   :header-rows: 1

   * - Argument
     - Purpose
   * - ``console=ttyS0``
     - places the kernel console on the serial port; the 115200 baud rate may be omitted
   * - ``root=/dev/vda1``
     - virtio disk partition that holds the root filesystem
   * - ``rw``
     - mounts root read-write
   * - ``nokaslr``
     - disables kernel address randomization for stable address comparison with gem5
   * - ``modprobe.blacklist=amdgpu``
     - stops the kernel or udev from auto-loading the driver before the ROM is written

``modprobe.blacklist=amdgpu`` only prevents auto-loading; the initialization service removes the runtime blacklist after writing the ROM, then runs ``modprobe`` with the fixed parameters.

IP block mask
-------------

Bit positions in ``ip_block_mask`` are IP discovery order indices, not the ``amd_ip_block_type`` enum values from ``amd_shared.h``. The driver checks ``(amdgpu_ip_block_mask & (1 << i))`` where ``i`` is the discovery order index. The MI300X discovery order under ROCm 7.0 DKMS is:

.. list-table::
   :header-rows: 1

   * - Index
     - IP block
     - Mask bit
     - Enabled in ``0x67``
   * - 0
     - ``soc15_common``
     - ``0x01``
     - yes
   * - 1
     - ``gmc_v9_0``
     - ``0x02``
     - yes
   * - 2
     - ``vega20_ih``
     - ``0x04``
     - yes
   * - 3
     - ``psp``
     - ``0x08``
     - no (disabled)
   * - 4
     - ``smu``
     - ``0x10``
     - no (disabled)
   * - 5
     - ``gfx_v9_4_3``
     - ``0x20``
     - yes
   * - 6
     - ``sdma_v4_4_2``
     - ``0x40``
     - yes
   * - 7
     - ``vcn_v4_0_3``
     - ``0x80``
     - no (not needed)
   * - 8
     - ``jpeg_v4_0_3``
     - ``0x100``
     - no (not needed)

Bit layout of ``0x67``:

.. code-block:: text

   0x67 = 0110_0111 (binary)
          ||||_||||
          |||| |||+-- bit 0: soc15_common  (enabled)
          |||| ||+--- bit 1: gmc_v9_0      (enabled)
          |||| |+---- bit 2: vega20_ih     (enabled)
          |||| +----- bit 3: psp           (DISABLED)
          |||+------- bit 4: smu           (DISABLED)
          ||+-------- bit 5: gfx_v9_4_3    (enabled)
          |+--------- bit 6: sdma_v4_4_2   (enabled)
          +---------- bit 7: vcn_v4_0_3    (disabled)

.. list-table::
   :header-rows: 1

   * - Mask
     - Binary
     - Enabled IP blocks
     - Use
   * - ``0x67``
     - ``0110_0111``
     - common, GMC, IH, GFX, SDMA
     - value used by cosim
   * - ``0x6f``
     - ``0110_1111``
     - common, GMC, IH, PSP, GFX, SDMA
     - wrong value; enabling PSP panics the kernel
   * - ``0xff``
     - ``1111_1111``
     - all blocks including PSP and SMU
     - real hardware only

Initialization order
--------------------

``cosim-gpu-initialize.service`` runs ``/usr/local/bin/cosim-gpu-initialize.sh`` once at guest boot, in this order:

.. list-table::
   :header-rows: 1

   * - Step
     - Action
   * - 1
     - export ``LD_LIBRARY_PATH``, ``HSA_ENABLE_INTERRUPT=0`` and ``HCC_AMDGPU_TARGET=gfx942``
   * - 2
     - write ``mi300.rom`` to ``0xC0000`` through ``/dev/mem``
   * - 3
     - link ``mi300_discovery`` as ``ip_discovery.bin``
   * - 4
     - remove the runtime ``modprobe.blacklist`` left by the kernel command line
   * - 5
     - run ``modprobe amdgpu`` with the parameters above, falling back to ``insmod`` of the DKMS module
   * - 6
     - check that every AMD PCI device has a DRM card and exit non-zero otherwise

Verification and sources
------------------------

``tests/test_modprobe_params.sh`` checks the image recipe's ``cosim_gpu_initialize.sh`` and requires every ``modprobe`` or ``insmod`` line to carry the six parameters:

.. code-block:: bash

   just check-modprobe-params

Sources of the definitions:

- ``resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/files/cosim_gpu_initialize.sh``: guest initialization script and default parameters.

- ``resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/files/cosim-gpu-initialize.service``: boot-time unit.

- ``resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/provision.yml``: installed locations of the ROM, discovery firmware and DKMS module.

- ``tests/test_modprobe_params.sh``: regression check for the parameter set.

Update the guest script, the tables above and the check that runs on that script in the same change.

Related pages
-------------

- Topology and vHost fields: :doc:`topology_schema`

- Troubleshooting related failures: :doc:`known_issues`

- Guest dependency files and image paths: :doc:`files_and_artifacts`

- Guest driver requirements: :ref:`sim-guest-driver`

- GPU address translation: :ref:`sim-gem5-address-translation`

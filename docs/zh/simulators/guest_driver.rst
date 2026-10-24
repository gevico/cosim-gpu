.. SPDX-License-Identifier: Apache-2.0

.. _sim-guest-driver:

客户机驱动要求
===============

本页说明协同仿真对客户机内核、amdgpu 驱动参数和 ROM 写入顺序的要求。完整参数表与取值理由以 :ref:`ref-guest-parameters`\ 为准，驱动开发细节见内核源码。

镜像与驱动前提
---------------

- 客户机镜像需要与内核版本匹配的 amdgpu DKMS 模块（ROCm 7.0），以及 ``amddrm_exec``\ 等同组模块；缺少模块会导致 TTM 初始化失败。
- IP discovery 固件位于 ``/usr/lib/firmware/amdgpu/mi300_discovery``\ ，因此 ``discovery=2``\ 可以从磁盘文件读取 IP 信息。
- VBIOS 文件位于 ``/root/roms/mi300.rom``\ ，需要在加载驱动前写入共享内存。
- 自动加载由 ``/lib/systemd/system/cosim-gpu-initialize.service``\ 和 ``/usr/local/bin/cosim-gpu-initialize.sh``\ 完成，顺序是写 ROM、再 ``modprobe``\ 。

内核命令行
-----------

样例 vHost 模板 ``resources/vhosts/qemu.yaml``\ 使用以下命令行：

.. code-block:: text

   console=ttyS0 root=/dev/vda1 rw nokaslr modprobe.blacklist=amdgpu

``modprobe.blacklist=amdgpu``\ 防止 PCI 子系统在 ROM 写入共享内存之前自动加载驱动。vHost 模板会把 vHost 的 ``cmdline``\ 与设备 ``guest_hints.cmdline``\ 拼接后传给 QEMU 的 ``-append``\ 。

驱动参数
---------

.. code-block:: bash

   modprobe amdgpu ip_block_mask=0x67 ppfeaturemask=0 dpm=0 audio=0 ras_enable=0 discovery=2

- ``ip_block_mask=0x67``\ ：只启用 common、GMC、IH、GFX 和 SDMA，禁用 PSP 与 SMU；使用 ``0x6f``\ 会启用 PSP 并导致初始化失败。
- ``ppfeaturemask=0``\ 与 ``dpm=0``\ ：协同仿真没有电源管理硬件，关闭 PowerPlay 与动态电源管理。
- ``audio=0``\ ：没有音频硬件。
- ``ras_enable=0``\ ：避免最小化 VBIOS 下 ``atom_context``\ 为空导致的空指针崩溃。
- ``discovery=2``\ ：从磁盘上的固件文件做 IP discovery，而不是读 GPU ROM 或寄存器。

ROM 写入顺序
-------------

``modprobe``\ 之前必须执行：

.. code-block:: bash

   dd if=/root/roms/mi300.rom of=/dev/mem bs=1k seek=768 count=128

该命令把 128 KiB 的 MI300X VBIOS 写到物理地址 ``0xC0000``\ 至 ``0xDFFFF``\ ，gem5 的 ``AMDGPUDevice::readROM()``\ 从共享客户机内存读取该区域。之所以必须显式写入，是因为 amdgpu 的五种 BIOS 发现路径在协同仿真下全部失败：

.. list-table::
   :header-rows: 1

   * - BIOS 发现路径
     - 失败原因
   * - ``amdgpu_atrm_get_bios()``
     - QEMU Q35 没有 ACPI ATRM 方法。
   * - ``amdgpu_acpi_vfct_bios()``
     - 没有 ACPI VFCT 表。
   * - ``amdgpu_read_bios_from_rom()``
     - 通过 SMU 寄存器读取，但 SMU 被 ``ip_block_mask=0x67``\ 禁用。
   * - ``amdgpu_read_platform_bios()``
     - 没有平台提供的 ROM。
   * - ``amdgpu_read_disabled_bios()``
     - 协同仿真下不可用。

自动加载与手动恢复
-------------------

正常启动时 ``cosim-gpu-initialize.service``\ 会自动完成 ROM 写入与驱动加载。需要手动恢复时：

.. code-block:: bash

   dd if=/root/roms/mi300.rom of=/dev/mem bs=1k seek=768 count=128
   modprobe amdgpu ip_block_mask=0x67 ppfeaturemask=0 dpm=0 audio=0 ras_enable=0 discovery=2
   dmesg | grep -i amdgpu | tail -20

验证方式
---------

.. code-block:: bash

   # 驱动是否加载，是否识别出 gfx942
   lsmod | grep amdgpu
   dmesg | grep -i -E "amdgpu|gfx942" | tail -30
   # IP discovery 与队列状态
   rocminfo | head -40
   rocm-smi
   # 自动加载服务是否成功
   systemctl status cosim-gpu-initialize.service

能够看到 MI300X 设备、``gfx942``\ 代理和可用的 ROCm 队列，说明功能路径已经打通。首个 HIP 程序的验证步骤见 :ref:`gs-verify-guest`\ 。

常见失败
---------

.. list-table::
   :header-rows: 1

   * - 症状
     - 首先检查
     - 处理
   * - ``modprobe``\ 时空指针崩溃
     - ROM 是否已写入、``ras_enable=0``
     - 按顺序执行 ROM 写入与 ``modprobe``\ 。
   * - ``PSP load tmr failed``
     - ``ip_block_mask``
     - 使用 ``0x67``\ 而不是 ``0x6f``\ 。
   * - ``Failed to init DRM client: -13``
     - 镜像中是否存在 ``amddrm_exec.ko.zst``
     - 用 ``just build-disk``\ 重建镜像。
   * - ``insmod``\ 内核版本不匹配
     - DKMS 模块与 ``uname -r``
     - 重建或更换匹配的镜像。
   * - ``cosim-gpu-initialize.service``\ 失败
     - ``journalctl -u cosim-gpu-initialize``
     - 按日志修复后手动执行上面的命令。

源码与依据
-----------

- 自动加载脚本：``resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/files/cosim_gpu_initialize.sh``\ 。
- 启动 vHost：``resources/vhosts/qemu.yaml``\ 。
- 驱动侧 ROM 读取：``third_party/gem5/src/dev/amdgpu/amdgpu_device.cc``\ 中的 ``readROM()``\ 。
- 参数唯一事实源：:ref:`ref-guest-parameters`\ 。

相关页面
---------

- :doc:`qemu/vhost`\ ：客户机的启动方式。
- :doc:`gem5/mi300x_pci`\ ：ROM BAR 与 VGA ROM 窗口。
- :doc:`debugging_models`\ ：驱动加载后的模型侧调试。
- :ref:`ref-guest-parameters`\ ：modprobe、dd 与 IP mask 参考。
- :ref:`ref-known-issues`\ ：完整已知问题清单。
- :ref:`gs-verify-guest`\ ：验证客户机与首个 HIP 程序。

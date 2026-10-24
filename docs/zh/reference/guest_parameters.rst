.. SPDX-License-Identifier: Apache-2.0

.. _ref-guest-parameters:

客户机参数
==========

本页是 cosim 客户机驱动参数的唯一事实源：amdgpu 模块参数、VGA ROM 写入、内核命令行与 IP block mask 都在这里定义。其他章节只说明何时执行这些步骤并链接本页。

amdgpu modprobe 参数
--------------------

六个参数缺一不可，完整命令为：

.. code-block:: bash

   modprobe amdgpu ip_block_mask=0x67 ppfeaturemask=0 dpm=0 audio=0 ras_enable=0 discovery=2

.. list-table::
   :header-rows: 1

   * - 参数
     - 值
     - 必需
     - 作用
   * - ``ip_block_mask``
     - ``0x67``
     - 是
     - 启用 common、GMC、IH、GFX、SDMA，禁用 PSP（bit 3）与 SMU（bit 4）；掩码含义见下文
   * - ``ppfeaturemask``
     - ``0``
     - 是
     - 禁用全部 PowerPlay 特性；cosim 没有电源管理硬件
   * - ``dpm``
     - ``0``
     - 是
     - 禁用动态电源管理
   * - ``audio``
     - ``0``
     - 是
     - 禁用 HDMI/DP 音频；cosim 没有音频硬件
   * - ``ras_enable``
     - ``0``
     - 是
     - 禁用 RAS；避免精简 VBIOS（约 3 KB）下 ``atom_context`` 为空时崩溃
   * - ``discovery``
     - ``2``
     - 是
     - 从磁盘固件文件读取 IP discovery，而不是从 GPU ROM/寄存器读取

.. warning::

   使用 ``ip_block_mask=0x6f`` 会启用 PSP 固件加载并导致内核 panic；cosim 使用 ``0x67``。

.. warning::

   ``ras_enable=0`` 是必需参数。缺少它时 ``amdgpu_ras_init`` 会在 ``atom_context`` 为空的情况下调用 ``amdgpu_atom_parse_data_header``，触发空指针崩溃。

VGA ROM 写入
------------

在 ``modprobe`` 之前，把 VBIOS 写入客户机物理地址 ``0xC0000``：

.. code-block:: bash

   dd if=/root/roms/mi300.rom of=/dev/mem bs=1k seek=768 count=128

.. list-table::
   :header-rows: 1

   * - 参数
     - 值
     - 含义
   * - ``if``
     - ``/root/roms/mi300.rom``
     - 客户机镜像内的 ROM 文件
   * - ``of``
     - ``/dev/mem``
     - 物理内存设备
   * - ``bs``
     - ``1k``
     - 块大小 1024 字节
   * - ``seek``
     - ``768``
     - 跳到 768 乘 1024，即物理地址 ``0xC0000``
   * - ``count``
     - ``128``
     - 写入 128 乘 1024，即 128 KiB

写入范围是 ``0xC0000`` 到 ``0xDFFFF``，落在共享客户机内存中。gem5 的 ``AMDGPUDevice::readROM()`` 通过 ``system->getPhysMem()`` 从该地址读取 ROM，因此这一步必须在 ``modprobe`` 之前完成。amdgpu 驱动的五种 BIOS 发现方式在 cosim 下全部失败：

.. list-table::
   :header-rows: 1

   * - BIOS 发现方式
     - 在 cosim 下失败的原因
   * - ``amdgpu_atrm_get_bios()``
     - QEMU Q35 没有 ACPI ATRM 方法
   * - ``amdgpu_acpi_vfct_bios()``
     - 没有 ACPI VFCT 表
   * - ``amdgpu_read_bios_from_rom()``
     - 通过 SMU 寄存器读取，而 SMU 被 ``0x67`` 禁用
   * - ``amdgpu_read_platform_bios()``
     - 没有平台提供的 ROM
   * - ``amdgpu_read_disabled_bios()``
     - 在 cosim 下不可用

内核命令行
----------

客户机内核使用以下命令行启动（记录在 vHost 的 ``cmdline`` 中）：

.. code-block:: text

   console=ttyS0 root=/dev/vda1 rw nokaslr modprobe.blacklist=amdgpu

.. list-table::
   :header-rows: 1

   * - 参数
     - 作用
   * - ``console=ttyS0``
     - 把内核控制台放到串口；115200 波特率可省略
   * - ``root=/dev/vda1``
     - root 文件系统所在的 virtio 磁盘分区
   * - ``rw``
     - 以读写方式挂载 root
   * - ``nokaslr``
     - 关闭内核地址随机化，便于按固定地址对照 gem5 侧行为
   * - ``modprobe.blacklist=amdgpu``
     - 阻止内核或 udev 在 ROM 写入前自动加载驱动

``modprobe.blacklist=amdgpu`` 只用于阻止自动加载；初始化服务会在写入 ROM 后删除该运行时黑名单，再执行带固定参数的 ``modprobe``。

IP block mask
-------------

``ip_block_mask`` 的位位置使用 IP discovery 的检测顺序索引，而不是 ``amd_shared.h`` 中 ``amd_ip_block_type`` 枚举值。驱动检查 ``(amdgpu_ip_block_mask & (1 << i))``，其中 ``i`` 是检测顺序索引。MI300X 在 ROCm 7.0 DKMS 下的检测顺序为：

.. list-table::
   :header-rows: 1

   * - 索引
     - IP block
     - 掩码位
     - 在 ``0x67`` 中是否启用
   * - 0
     - ``soc15_common``
     - ``0x01``
     - 是
   * - 1
     - ``gmc_v9_0``
     - ``0x02``
     - 是
   * - 2
     - ``vega20_ih``
     - ``0x04``
     - 是
   * - 3
     - ``psp``
     - ``0x08``
     - 否（禁用）
   * - 4
     - ``smu``
     - ``0x10``
     - 否（禁用）
   * - 5
     - ``gfx_v9_4_3``
     - ``0x20``
     - 是
   * - 6
     - ``sdma_v4_4_2``
     - ``0x40``
     - 是
   * - 7
     - ``vcn_v4_0_3``
     - ``0x80``
     - 否（非必需）
   * - 8
     - ``jpeg_v4_0_3``
     - ``0x100``
     - 否（非必需）

``0x67`` 的位布局：

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

   * - 掩码
     - 二进制
     - 启用的 IP 块
     - 用途
   * - ``0x67``
     - ``0110_0111``
     - common、GMC、IH、GFX、SDMA
     - cosim 使用值
   * - ``0x6f``
     - ``0110_1111``
     - common、GMC、IH、PSP、GFX、SDMA
     - 错误值；启用 PSP 会导致内核 panic
   * - ``0xff``
     - ``1111_1111``
     - 包含 PSP、SMU 在内的全部块
     - 仅适用于真实硬件

初始化顺序
----------

``cosim-gpu-initialize.service`` 在客户机启动时执行一次 ``/usr/local/bin/cosim-gpu-initialize.sh``，顺序如下：

.. list-table::
   :header-rows: 1

   * - 步骤
     - 动作
   * - 1
     - 设置 ``LD_LIBRARY_PATH``、``HSA_ENABLE_INTERRUPT=0``、``HCC_AMDGPU_TARGET=gfx942``
   * - 2
     - 把 ``mi300.rom`` 写入 ``/dev/mem`` 的 ``0xC0000``
   * - 3
     - 把 ``mi300_discovery`` 链接为 ``ip_discovery.bin``
   * - 4
     - 删除内核命令行留下的运行时 ``modprobe.blacklist``
   * - 5
     - 执行带上述参数的 ``modprobe amdgpu``，失败时回退到 ``insmod`` DKMS 模块
   * - 6
     - 检查每个 AMD PCI 设备都有对应 DRM card，否则以非零状态退出

校验与来源
----------

``tests/test_modprobe_params.sh`` 检查镜像 recipe 中的 ``cosim_gpu_initialize.sh``，要求每处 ``modprobe``/``insmod`` 都包含上述六个参数：

.. code-block:: bash

   just check-modprobe-params

参数定义来源：

- ``resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/files/cosim_gpu_initialize.sh``：客户机初始化脚本与默认参数。

- ``resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/files/cosim-gpu-initialize.service``：开机执行单元。

- ``resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/provision.yml``：ROM、discovery 固件与 DKMS 模块的安装位置。

- ``tests/test_modprobe_params.sh``：参数集合的回归检查。

修改参数时同时更新客户机脚本、本页表格以及在该脚本上执行的检查。

相关页面
--------

- 拓扑与 vHost 字段：:doc:`topology_schema`

- 相关故障的处理：:doc:`known_issues`

- 客户机依赖文件与镜像内路径：:doc:`files_and_artifacts`

- 客户机驱动要求：:ref:`sim-guest-driver`

- GPU 地址翻译：:ref:`sim-gem5-address-translation`

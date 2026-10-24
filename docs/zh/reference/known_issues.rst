.. SPDX-License-Identifier: Apache-2.0

.. _ref-known-issues:

已知问题
========

本页是问题现象、根因与修复的唯一事实源。参数、格式和路径不在此重复：涉及驱动参数时链接 :doc:`guest_parameters`，涉及 GART 时链接 :doc:`gart_format`。

快速诊断
--------

先按现象定位到最小检查项，再进入下方的完整条目。

.. list-table::
   :header-rows: 1

   * - 现象
     - 首先检查
   * - gem5 进程启动后立即退出
     - 查看进程日志；独立 shell 路径使用 ``docker logs <container>``
   * - QEMU 连接失败
     - 确认 gem5 已就绪、socket 已创建且可访问
   * - ``psp_gpu_reset`` 空指针
     - 检查 ``ip_block_mask`` 是否为 ``0x67``
   * - 大量 GART translation not found
     - 确认使用最新构建的 gem5，再检查 :doc:`gart_format` 的回退逻辑
   * - SDMA ring test 返回 -110
     - 检查 ``sdma_delay`` 是否已降到 ``1000``
   * - hipcc 找不到 ROCm device library
     - 检查 ``/opt/rocm/lib``，并使用 ``--offload-arch=gfx942``
   * - MMIO 读取全为零
     - gem5 未连接或已经崩溃
   * - ``insmod`` 报错
     - 内核版本与 DKMS 模块不匹配
   * - ``cosim-gpu-initialize.service`` 失败
     - ``journalctl -u cosim-gpu-initialize``
   * - BAR 布局 probe 返回 -12
     - 检查 ``MI300XVfioUser`` 导出的 BAR 区域描述

问题目录
--------

以下条目标题中的编号与历史问题编号对应，便于交叉引用。

4.1 VGA ROM 空指针崩溃
~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 项
     - 内容
   * - 症状
     - ``modprobe amdgpu`` 触发内核空指针崩溃，位置在 ``amdgpu_atom_parse_data_header+0x1b``；调用链为 ``amdgpu_ras_init`` 经 ``amdgpu_atomfirmware_mem_ecc_supported`` 到 ``amdgpu_atom_parse_data_header``，``RAX=0``。
   * - 根因
     - 五种 BIOS 发现方式在 cosim 下全部失败，驱动打印 ``Unable to locate a BIOS ROM`` 后继续执行，RAS 初始化路径在 ``atom_context`` 为空时仍调用解析函数。
   * - 修复
     - 在 ``modprobe`` 之前写入 ROM，命令见 :doc:`guest_parameters` 的 VGA ROM 一节；``cosim-gpu-initialize.service`` 会自动完成。

4.2 PSP / SMU 固件加载失败
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 项
     - 内容
   * - 症状
     - 出现 ``PSP load tmr failed!``、``hw_init of IP block <psp> failed -22`` 或 ``Fatal error during GPU init``。
   * - 根因
     - ``ip_block_mask=0x6f`` 启用了 PSP（检测顺序索引 3），但 cosim 不模拟 PSP 硬件。
   * - 修复
     - 使用 ``ip_block_mask=0x67`` 同时禁用 PSP 与 SMU，见 :doc:`guest_parameters` 的 IP block mask 一节。

4.3 协同仿真模式下 GART 表未填充
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 项
     - 内容
   * - 症状
     - 出现大量 ``GART translation for X not found`` 警告；PM4 读到全零内存（opcode 0x0）；KIQ ring test 超时。
   * - 根因
     - VRAM 由共享内存支撑，驱动对 VRAM 的写入绕过 gem5 内存系统，``AMDGPUVM::gartTable`` 不会通过 ``writeFrame()`` 被填充。
   * - 修复
     - 翻译路径在 ``gartTable`` 未命中时直接从共享 VRAM 读取 PTE，细节见 :doc:`gart_format` 的回退查找。

4.4 GART 未映射页崩溃
~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 项
     - 内容
   * - 症状
     - ``hipMalloc`` 成功后 gem5 段错误，并伴随重复的 ``GART translation for 0x3fff800000000 not found``；无限 DMA 重试导致内存耗尽。
   * - 根因
     - GPU PM4/SDMA 引擎会 DMA 到驱动尚未映射的 GART 页（PTE 为 0），原始实现在此创建 ``GenericPageTableFault``，DMA 回调链会无限重试同一地址。
   * - 修复
     - 未映射的 GART 页映射到 sink（``paddr=0``）：读返回零、写被丢弃。``ptStart`` 处的第一页本身未映射属于正常现象。

4.5 SDMA ring 测试超时
~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 项
     - 内容
   * - 症状
     - 驱动初始化期间 SDMA ring test 返回 ``-110`` （``-ETIMEDOUT``）：``sdma v4_4_2: ring 0 test failed (-110)``。
   * - 根因
     - ``sdma_delay`` 默认为 ``1e9`` ticks，在 cosim 下约等于 500 ms，超过驱动约 200 ms 的超时窗口。
   * - 修复
     - 把 ``sdma_delay`` 从 ``1e9`` 降到 ``1000`` ticks，并把 ``KEEPALIVE_INTERVAL`` 增大到 ``1e9`` 以避免 keepalive 干扰时序。

4.6 VRAM 地址 GART 翻译错误
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 项
     - 内容
   * - 症状
     - 地址 ``0x1f72fa8000`` 产生 861000 次以上 GART 翻译错误，随后内存耗尽并段错误。
   * - 根因
     - SDMA rptr 回写与 PM4 ``RELEASE_MEM`` 的目标地址可能指向 VRAM（小于 16 GiB）；这些地址经 ``getGARTAddr()`` 处理后查不到对应页表项。
   * - 修复
     - 三层防护：PM4 的 ``writeData()``、``releaseMem()``、``queryStatus()`` 检查 ``isVRAMAddress()`` 并路由到 GPU 内存管理器；SDMA 对 VRAM 地址跳过 ``getGARTAddr()``；GART 兜底把 VRAM 地址映射到 sink。

4.7 共享内存文件偏移量不匹配
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 项
     - 内容
   * - 症状
     - GART 页表项读出全为零，PM4 opcode 0x0 重复出现。
   * - 根因
     - QEMU Q35 在 8 GiB RAM 时把 ``below_4g`` 固定为 2 GiB，而 gem5 配置按 3 GiB 以下、5 GiB 以上处理，4 GiB 以上数据的文件偏移相差 1 GiB。
   * - 修复
     - ``mi300_cosim.py`` 复刻 Q35 的拆分逻辑：``below_4g = min(total_mem, 0x80000000 if total_mem >= 0xB0000000 else 0xB0000000)``。

4.8 定时器溢出崩溃
~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 项
     - 内容
   * - 症状
     - 运行数十亿 tick 后 gem5 因 ``curTick()`` 整数溢出崩溃，``schedule()`` 断言失败。
   * - 根因
     - RTC 与 PIT 定时器持续调度事件，在长期运行的 cosim 会话中耗尽 tick 计数。
   * - 修复
     - ``Cmos`` 增加 ``disable_rtc_events`` 参数、``I8254`` 增加 ``disable_timer_events`` 参数，并在 ``mi300_cosim.py`` 中禁用；cosim 桥接的 keepalive 事件避免事件队列为空。

4.9 PM4ReleaseMem.dataSelect panic
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 项
     - 内容
   * - 症状
     - gem5 panic，报 ``Unimplemented PM4ReleaseMem.dataSelect``。
   * - 根因
     - ``pm4_packet_processor.cc`` 只实现了 ``dataSelect == 1`` （32 位写入），驱动在 GFX 初始化时使用其他模式。
   * - 修复
     - 补齐常见取值：0 表示不写数据、1 表示 32 位写入、2 表示 64 位写入、3 表示 64 位 GPU 时钟计数，其他值告警并按空操作处理。

4.10 未处理的 PM4 操作码
~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 项
     - 内容
   * - 症状
     - gem5 在遇到未识别的 PM4 opcode 时崩溃。
   * - 根因
     - ``ACQUIRE_MEM`` （``0x58``）与 ``SET_RESOURCES`` （``0xA0``）未被处理。
   * - 修复
     - 两者已加入 ``pm4_defines.hh``，并在 ``pm4_packet_processor.cc:decodeHeader()`` 中按跳过并继续（NOP）处理。

4.11 PCI class code 不匹配
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 项
     - 内容
   * - 症状
     - amdgpu 驱动跳过 ``0xC0000`` 处的 legacy VGA ROM 检查。
   * - 根因
     - PCI class 为 ``PCI_CLASS_DISPLAY_OTHER`` （``0x0380``）而不是 ``PCI_CLASS_DISPLAY_VGA`` （``0x0300``）。
   * - 修复
     - 把设备 class 改为 ``PCI_CLASS_DISPLAY_VGA``，内核会把该地址范围识别为带 shadowed ROM 的视频设备。

4.12 QEMU 串口控制台冲突
~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 项
     - 内容
   * - 症状
     - 同时使用 ``-serial unix:...`` 与 ``-nographic`` 时客户机没有串口输出。
   * - 根因
     - ``-nographic`` 隐含 ``-serial mon:stdio``，创建映射到 stdio 的 serial0；显式 ``-serial unix:...`` 变成 serial1（ttyS1），而内核使用 ``console=ttyS0``。
   * - 修复
     - 只使用 ``-nographic``；需要程序化访问时在 ``screen`` 中运行 QEMU。

4.13 gem5 链接时内存不足
~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 项
     - 内容
   * - 症状
     - 即使使用 ``-j2``，链接器仍被 OOM killer 终止。
   * - 根因
     - 默认链接器内存开销过大。
   * - 修复
     - 使用 ``just build-gem5 1 GOLD_LINKER=True --linker=gold``。

4.14 DRM client 错误 -13（缺少 DKMS 模块）
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 项
     - 内容
   * - 症状
     - 驱动初始化出现 ``Failed to init DRM client: -13`` 后内核 panic，崩溃点在 ``ttm_resource_move_to_lru_tail``。
   * - 根因
     - 磁盘镜像缺少 ``amddrm_exec.ko.zst`` 这个 DKMS 模块，TTM 内存管理器初始化失败，``drm_dev_enter()`` 返回 ``-EACCES``。
   * - 修复
     - 用 ``just build-disk`` 重新构建磁盘镜像，并确认 ``/lib/modules/6.8.0-124-generic/updates/dkms/amddrm_exec.ko.zst`` 存在。

4.15 驱动 hw_init 失败后 rmmod 导致 oops
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 项
     - 内容
   * - 症状
     - 驱动 ``hw_init`` 失败后执行 ``rmmod amdgpu`` 触发内核 oops（``kgd2kfd_device_exit`` 中的 page fault），模块停留在 busy 状态。
   * - 根因
     - 部分初始化后的清理路径不够健壮。
   * - 修复
     - 没有可靠绕过方式，需要重启整个 cosim 环境：结束 QEMU、重启 gem5 进程、再启动 QEMU。

来源与维护
----------

问题记录来自 cosim 调试过程与模型实现变更。修复方式落地后应同步更新对应实现与本节条目：

- 驱动参数与 ROM 写入：:doc:`guest_parameters`。

- GART 与地址翻译：:doc:`gart_format`、:ref:`sim-gem5-address-translation`。

- gem5 模型行为与调试标志：:ref:`sim-gem5-model`、:ref:`sim-debugging-models`。

- 会话日志、verdict 与清理：:ref:`launcher-debugging-sessions`。

报告新问题时附上现象、复现命令、gem5 版本或提交、驱动 dmesg 与关键日志片段，再按上述分类归入本页。

相关页面
--------

- 客户机参数：:doc:`guest_parameters`

- GART 格式：:doc:`gart_format`

- 版本矩阵：:doc:`version_matrix`

- 文件与会话目录：:doc:`files_and_artifacts`

- 遗留 launcher 参数：:doc:`legacy_launcher_flags`

- 客户机驱动要求：:ref:`sim-guest-driver`

- 模型调试：:ref:`sim-debugging-models`

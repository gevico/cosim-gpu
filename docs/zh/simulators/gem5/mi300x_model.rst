.. SPDX-License-Identifier: Apache-2.0

.. _sim-gem5-model:

MI300X 性能模型
================

本页说明 gem5 中 MI300X 模型的组件、命令与中断路径以及时序相关的实现选择。PCI 接口见 :doc:`mi300x_pci`\ ，地址翻译见 :doc:`address_translation`\ 。

系统组成
---------

.. mermaid::

   flowchart TD
       Q[Host QEMU] -->|vfio-user| V[MI300XVfioUser]
       V --> A[AMDGPUDevice]
       A --> P[PM4PacketProcessor]
       A --> S[SDMAEngine]
       A --> I[InterruptHandler]
       A --> M[AMDGPUVM]
       A --> H[NBIO / SystemHub / SMU]
       P --> G[Shader 与 CU 阵列]
       S --> R[Ruby Disjoint_VIPER]
       G --> R

launcher 传入的参数
--------------------

适配器 ``gem5-mi300x``\ 启动配置脚本时传入以下参数；取值来自内存布局和设备 ``args``\ 。

.. list-table::
   :header-rows: 1

   * - 参数
     - 作用
   * - ``--outdir``
     - 把 ``m5out``\ 放在设备工作目录下。
   * - ``--debug-flags``
     - 可选的 gem5 调试标志，来自 ``args.gem5_debug_flags``\ 。
   * - ``--listener-mode=off``
     - 关闭 gem5 的交互监听。
   * - ``--socket-path``
     - vfio-user Unix socket。
   * - ``--shared-pool``
     - 机器内存池文件，同时承载客户机 RAM 与 VRAM。
   * - ``--pool-vram-offset``
     - 本 GPU 的 VRAM 区域在 pool 中的偏移。
   * - ``--dgpu-mem-size``
     - 本 GPU 的 VRAM 大小，来自内存布局。
   * - ``--mem-size``
     - 客户机 RAM 大小。
   * - ``--host-memory-ranges``
     - 客户机物理地址区间与 pool 偏移的 JSON 描述。
   * - ``--num-compute-units``
     - 每个 GPU 的计算单元数，来自 ``args.num_compute_units``\ 。
   * - ``--num-gpus=1``
     - YAML 适配器每个进程只启动一个 GPU。

组件职责
---------

.. list-table::
   :header-rows: 1

   * - 组件
     - 源码
     - 职责
   * - ``MI300XVfioUser``
     - ``mi300x_vfio_user.cc``
     - 配置空间、BAR、DMA 映射与中断，作为 libvfio-user 服务端。
   * - ``AMDGPUDevice``
     - ``amdgpu_device.cc``
     - MMIO 解码、ROM 读取、门铃处理、IP 块寄存器分发和 ``intrPost()``\ 。
   * - ``PM4PacketProcessor``
     - ``pm4_packet_processor.cc``
     - PM4 包解码，``writeData``\ 、``releaseMem``\ 、``queryStatus``\ ；VRAM 地址路由；未处理操作码按跳过处理。
   * - ``SDMAEngine``
     - ``sdma_engine.cc``
     - SDMA 包执行、读写、rptr 回写和 VRAM 地址处理。
   * - ``AMDGPUInterruptHandler``
     - ``interrupt_handler.cc``
     - 写入 IH ring 记录、更新写指针并请求中断。
   * - ``AMDGPUVM``
     - ``amdgpu_vm.cc``
     - AGP、GART、MMHUB 和用户上下文翻译；共享 VRAM 回退。
   * - Shader 与 CU 阵列
     - ``third_party/gem5/src/gpu/`` 与配置脚本
     - 每 GPU 的 CU 数由 ``num_compute_units``\ 控制，配合 GPUTLB 配置。
   * - Ruby ``Disjoint_VIPER``
     - ``third_party/gem5/configs/example/gpufs/Disjoint_VIPER.py``
     - GPU 缓存与内存层次，保留 Ruby 的请求处理和缓存行为。

命令与中断路径
---------------

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

- PM4 和 SDMA 根据地址与 VM 上下文选择设备内存或系统内存路径；系统内存访问共享客户机内存，设备内存访问 VRAM 区域。
- 完成标记和 IH 记录写入共享内存后，``AMDGPUDevice::intrPost()``\ 经 ``MI300XVfioUser``\ 触发 IRQ eventfd。
- 客户机通过共享内存读取 IH 记录与完成值，不依赖 gem5 的私有数据结构。

时序相关的实现选择
-------------------

- gem5 系统使用 ``atomic_noncaching``\ 内存模式，客户机内核由 QEMU 执行，gem5 只模拟 GPU 侧行为。
- SDMA 操作按 ``sdma_delay``\ 常数延迟调度，当前值为 1000 ticks；该值需适配驱动约 200 ms 的 ring test 超时窗口。
- ``MI300XVfioUser``\ 以 1e9 ticks 的间隔调度 keepalive，既保证事件队列不为空，也为 SDMA 处理留出时间。
- ``gem5.py``\ 关闭 CMOS RTC 和 8254 PIT 的事件调度（``disable_rtc_events``\ 、``disable_timer_events``\ ），避免长期运行时 tick 溢出。
- 时序行为由各组件的事件调度与 Ruby 模型共同决定；更换 CU 数、VRAM 大小或时钟会改变这些时序。

未建模部分
-----------

- PSP、SMU/电源管理、音频和 RAS 未建模；SMU 前缀寄存器由 ``AMDGPUSmu``\ 处理，但没有实际电源管理行为。
- gem5 侧没有 x86 内核，也没有 BIOS 发现流程；VBIOS 必须由客户机写入共享内存。
- PCIe switch、机器间 fabric 和多机互联不在当前模型中；进程内多 GPU 与 XGMI 见 :doc:`multi_gpu_xgmi`\ 。

源码与依据
-----------

- 配置脚本：``resources/devices/gpu/mi300x/gem5.py``\ 。
- 设备模型目录：``third_party/gem5/src/dev/amdgpu/``\ 。
- 调试标志定义：``third_party/gem5/src/dev/amdgpu/SConscript``\ 。
- 模型自测：``just test-gem5-mi300x``\ 运行 ``third_party/gem5/tests/mi300x/verify.py``\ 。

相关页面
---------

- :doc:`mi300x_pci`\ ：PCI/BAR 接口。
- :doc:`address_translation`\ ：GPU 地址翻译与共享 VRAM 回退。
- :doc:`multi_gpu_xgmi`\ ：多 GPU 与 XGMI。
- :doc:`../debugging_models`\ ：调试标志与常见模型问题。
- :ref:`arch-memory-model`\ ：共享内存与地址空间。

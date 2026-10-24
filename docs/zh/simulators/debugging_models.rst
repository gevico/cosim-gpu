.. SPDX-License-Identifier: Apache-2.0

.. _sim-debugging-models:

模型调试
=========

本页说明如何打开 gem5 的调试输出、在哪里读日志，以及 MI300X 模型常见问题的定位顺序。完整问题清单见 :ref:`ref-known-issues`\ 。

打开 gem5 调试输出
-------------------

.. list-table::
   :header-rows: 1

   * - 调试标志
     - 显示内容
   * - ``MI300XCosim``
     - vfio-user 消息、监听与中断交互。
   * - ``AMDGPUDevice``
     - MMIO 寄存器读写、ROM 访问、IH 指针。
   * - ``PM4PacketProcessor``
     - PM4 包解码与处理。
   * - ``SDMAEngine``
     - SDMA 操作与完成路径。
   * - ``SDMAData``
     - SDMA 包数据细节。
   * - ``AMDGPUMem``
     - GPU 内存管理器分配与访问。
   * - ``AMDGPUSystemHub``
     - SystemHub 访问。
   * - ``XGMIBridge``
     - 进程内多 GPU 的 xGMI 路由。

在 YAML 中通过设备的 ``args.gem5_debug_flags``\ 打开，适配器会把它渲染成 gem5 的 ``--debug-flags=...``\ 。也可以直接调用 gem5 时传 ``--debug-flags``\ ，并用 ``--debug-file``\ 指定输出文件；默认输出到 stdout，因此 launcher 管理的会话会把它收进 ``output.log``\ 。

.. code-block:: yaml

   templates:
     mi300x:
       kind: gem5-mi300x
       args:
         gem5_debug_flags: [MI300XCosim, AMDGPUDevice, PM4PacketProcessor]

日志位置
---------

.. list-table::
   :header-rows: 1

   * - 位置
     - 内容
   * - ``.cosim/<name>/m0/mi300x-0/output.log``
     - gem5 标准输出与标准错误，包含调试输出和警告。
   * - ``.cosim/<name>/m0/mi300x-0/m5out/``
     - gem5 统计与输出目录。
   * - ``.cosim/<name>/m0/vhost/serial.log``
     - 客户机串口日志，用于观察驱动侧行为。
   * - ``.cosim/<name>/verdict.json``
     - 会话级结果，先看它判断失败发生在哪个组件。
   * - ``docker logs``\ 与 ``/tmp/cosim-<run-id>.log``
     - 遗留 shell launcher 下 gem5 容器与 screen 的日志。

常见模型问题
-------------

.. list-table::
   :header-rows: 1

   * - 症状
     - 首先检查
     - 处理
   * - 大量 ``GART translation ... not found``\ 或 ``mapped to sink``
     - 共享 VRAM 偏移、PTE 内容、是否使用最新 gem5
     - 确认 pool 偏移与内存布局一致；零星期次警告可能正常，持续刷屏说明页表或偏移有问题。
   * - ``Unimplemented PM4ReleaseMem.dataSelect``\ panic
     - 驱动使用的 dataSelect 值
     - 模型实现了 0、1、2、3；其他值需要扩展 ``pm4_packet_processor.cc``\ 。
   * - 未知 PM4 操作码
     - 操作码编号
     - ``ACQUIRE_MEM``\ 与 ``SET_RESOURCES``\ 按跳过处理，其余需要补充实现或确认可安全跳过。
   * - SDMA ring test 返回 ``-110``
     - ``sdma_delay``\ 与 keepalive 间隔
     - 确认 ``sdma_delay``\ 为 1000 ticks，且没有额外阻塞事件队列。
   * - MMIO 读取全部返回 0
     - gem5 是否已连接、``output.log``\ 是否崩溃
     - 检查就绪标记与 socket；必要时只启用 ``MI300XCosim``\ 观察协议。
   * - BAR 布局探测错误 ``-12``
     - BAR 区域描述与大小
     - 检查 ``MI300XVfioUser``\ 的 BAR 设置和内存布局中的 VRAM 大小。
   * - 定时器溢出崩溃
     - RTC/PIT 事件是否禁用
     - ``mi300_cosim.py``\ 默认禁用 ``disable_rtc_events``\ 与 ``disable_timer_events``\ 。

调试工作流
-----------

1. 先用 ``cosim run --dry-run``\ 确认渲染出的 gem5 参数、socket、pool 偏移和 VRAM 大小符合预期。
2. 在设备 ``args.gem5_debug_flags``\ 中只打开一个维度的标志，重跑并观察 ``output.log``\ 。
3. 先看 ``verdict.json``\ 判断失败在哪个进程；再按 ``MI300XCosim``\ （协议）、``AMDGPUDevice``\ （寄存器）、``PM4PacketProcessor``\ / ``SDMAEngine``\ （命令）逐层缩小范围。
4. 用 ``just test-gem5-mi300x``\ 运行不依赖 QEMU 的模型自测，确认 pool 所有权与 GPU_VIPER 协议本身正常。
5. 修改模型后先做增量构建 ``just build-gem5 1``\ ，再重跑会话。

常用命令
---------

.. code-block:: bash

   # 使用开发构建重跑会话
   just run-topology-dev resources/machines/single-gpu.yaml
   # 过滤协议、地址翻译和致命错误
   grep -E "MI300XCosim|GART|panic|unimplemented" .cosim/<name>/m0/mi300x-0/output.log
   # 不依赖 QEMU 的模型自测（pool 所有权与 GPU_VIPER）
   just test-gem5-mi300x
   # 增量构建 gem5
   just build-gem5 1

源码与依据
-----------

- 调试标志定义：``third_party/gem5/src/dev/amdgpu/SConscript``\ 。
- vfio-user 服务端：``third_party/gem5/src/dev/amdgpu/mi300x_vfio_user.cc``\ 。
- PM4 与 SDMA：``third_party/gem5/src/dev/amdgpu/pm4_packet_processor.cc``\ 、``sdma_engine.cc``\ 。
- 模型自测：``third_party/gem5/tests/mi300x/verify.py``\ 。
- 调试参数：``third_party/gem5/src/python/m5/main.py``\ 中的 ``--debug-flags``\ 、``--debug-file``\ 和 ``--outdir``\ 。

相关页面
---------

- :doc:`gem5/mi300x_model`\ ：模型组件与命令路径。
- :doc:`gem5/address_translation`\ ：GART 警告的含义。
- :doc:`guest_driver`\ ：驱动侧失败与 ROM 顺序。
- :doc:`../launcher/debugging_sessions`\ ：会话级日志与 verdict。
- :ref:`ref-known-issues`\ ：完整已知问题清单。

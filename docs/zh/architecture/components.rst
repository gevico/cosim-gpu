.. SPDX-License-Identifier: Apache-2.0

.. _arch-components:

组件与职责
==========

系统由 Rust launcher、host QEMU、设备模型进程（gem5 或 QEMU）、vfio-user
连接和共享内存池组成。本页说明每部分的职责与边界。

总览
----

.. mermaid::

   flowchart LR
       Y[拓扑 YAML] --> L[cosim launcher]
       L --> H[Host QEMU]
       L --> G[gem5 MI300X 设备进程]
       L --> Q[QEMU 设备进程]
       H <-->|vfio-user| G
       H <-->|vfio-user| Q
       H --- P[机器内存池]
       G --- P
       Q --- P
       H --> Guest[Linux 客户机与 ROCm]

launcher 读取拓扑与 vHost，生成执行计划并监督进程；模拟器只在计划给出的
路径、参数与内存区域上运行。

组件职责
--------

.. list-table::
   :header-rows: 1

   * - 组件
     - 进程或库
     - 职责
   * - ``cosim`` launcher
     - 用户进程
     - 加载、校验、规划、运行与清理会话；不参与仿真计算
   * - ``cosim-topology``
     - Rust 库
     - YAML 解析与校验、模板展开、内存布局、启动参数渲染
   * - ``cosim-runtime``
     - Rust 库
     - 执行计划、会话资源、就绪探测、租约、verdict 与清理
   * - Host QEMU
     - host 进程
     - 运行客户机 CPU、内存与 PCIe，提供 QMP 与串口；功能仿真
   * - gem5 MI300X
     - 设备进程
     - MI300X 性能模型，作为 vfio-user 服务端；性能仿真
   * - QEMU 设备进程
     - 设备进程
     - 通过 ``x-vfio-user-server`` 导出 PCI 设备；功能仿真
   * - vfio-user
     - Unix socket 协议
     - QEMU host 与设备模型之间的桥
   * - 共享内存池
     - 文件
     - 客户机内存与设备区域，供 QEMU 与设备模型共同映射

QEMU：功能仿真
--------------

QEMU 在本系统中承担两个角色，二者都是功能仿真，不提供微架构时序：

- **vhost**：host QEMU 用 Q35 或 virt 机器、KVM 或 TCG 运行客户机 Linux，
  完成 PCIe 枚举，加载 amdgpu 驱动，并提供 QMP 与串口用于控制和观察。
- **device model**：设备 QEMU 进程使用 ``-machine x-remote`` 与
  ``-object x-vfio-user-server``，把 ``edu`` 这类 PCI 设备导出为 vfio-user
  服务端。模型保证寄存器与中断行为正确，不建模时序。

QEMU 不模拟 GPU 性能；MI300X 的时序由 gem5 提供。两类设备可以在同一台机器
中组合，机器目录中的 ``mixed-models`` 就是这种组合。

gem5：性能仿真
--------------

gem5 运行 MI300X 设备模型，通过 ``MI300XVfioUser`` 暴露配置空间、BAR、
DMA 映射与中断。模型覆盖：

- PM4 命令处理器与 SDMA 引擎；
- Shader 与 Compute Unit、Ruby 内存层次；
- 中断处理器与 GPU 地址翻译（GART、MMHUB、用户上下文）；
- GPU 命令队列、完成标记与 DMA 的数据通路。

联合仿真配置使用 ``StubWorkload``，只执行设备模型。YAML 适配器为每个 gem5
进程启动一个 GPU；gem5 配置自身支持的进程内多 GPU 模式不由 YAML 路径使用。

vfio-user：两者之间的桥
-----------------------

host QEMU 使用内置的 ``vfio-user-pci`` 客户端，设备侧由 gem5 的
``MI300XVfioUser``\ （libvfio-user）或 QEMU 的 ``x-vfio-user-server`` 提供
服务端。协议走 Unix socket，支持 PCI 配置空间、MMIO、DMA 映射与中断。
细节见 :doc:`vfio_user`。

支撑设施
--------

- **共享内存池**：每台机器一个文件，客户机内存在前，设备区域按对齐追加；
  布局写入 ``layout.json``，见 :doc:`memory_model`。
- **磁盘**：vHost 声明内核与磁盘；会话为每台机器创建 overlay 或直接使用
  指定镜像。
- **进程监督**：每个进程在独立进程组中启动，设备先于 host 启动，host 先于
  设备停止；细节见 :doc:`execution_flow`。
- **日志与 verdict**：运行目录保留计划、清单、各进程日志与
  ``verdict.json``，最后一行输出 ``[COSIM_VERDICT]``。

源码入口
--------

.. list-table::
   :header-rows: 1

   * - 路径
     - 内容
   * - ``crates/cosim-topology/src/``
     - YAML 类型、校验、布局与适配器
   * - ``crates/cosim-runtime/src/``
     - 计划、会话、探测、资源与清理
   * - ``third_party/gem5/configs/example/gpufs/mi300_cosim.py``
     - MI300X 对象、池与 vfio-user 参数
   * - ``third_party/gem5/src/dev/amdgpu/``
     - PM4、SDMA、中断、GPU VM 与 vfio-user 服务端
   * - ``third_party/qemu/hw/remote/vfio-user-obj.c``
     - QEMU device server 接口
   * - ``resources/``
     - 镜像配方，以及并列的 vHost、设备、机器和集群配置目录

相关页面
--------

- :doc:`execution_flow`
- :doc:`memory_model`
- :doc:`vfio_user`
- :ref:`QEMU 与 gem5：功能仿真与性能仿真 <sim-index>`
- :ref:`MI300X 性能模型 <sim-gem5-model>`

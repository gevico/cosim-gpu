.. SPDX-License-Identifier: Apache-2.0

.. _glossary:

术语表
======

本页统一文档和代码中使用的术语。概念说明见 :ref:`arch-index`，字段定义见
:ref:`ref-topology-schema`。

拓扑与运行
----------

拓扑（topology）
  描述若干台机器的 YAML 文档，包含 ``version``、``imports``、
  ``templates``、``kinds`` 和 ``machines`` 字段。

机器（machine）
  一个 ``vhost``、挂在它上面的全部 ``device`` 以及一个共享内存池组成的
  运行单元。拓扑中的 ``machines`` 列表经 ``count`` 展开后得到具体的机器
  实例，例如 ``m0`` 到 ``m3``。

vHost
  运行客户机 Linux 的 QEMU 进程。vHost 由 vHost 模板声明，负责 CPU、内存、PCIe
  枚举、QMP 和串口端点，并作为 vfio-user 客户端连接设备。客户机操作系统只是
  QEMU 内部运行的 Linux，不是拓扑对象或额外的配置层。

device
  以原生进程运行、通过 vfio-user 向所属机器的 vHost 提供 PCI 设备的进程。设备由
  ``gem5-mi300x`` 或 ``qemu-device`` 适配器启动，MI300X 适配器为每个
  进程启动一个 GPU。

会话（session）
  ``cosim run`` 创建的资源树：运行目录、共享内存池目录、全部进程、锁、磁盘
  overlay 以及日志。会话以临时名称准备、一次性发布，结束后写入 verdict。

执行计划（plan）
  ``cosim run --dry-run`` 输出的完整执行描述，记录程序、参数、环境、依赖、就绪探测、
  内存区域、磁盘目标和锁文件路径；``cosim run`` 直接消费该计划。

内存池（pool）
  每台机器一个共享内存文件，客户机内存位于开头，设备区域按声明顺序排列。QEMU 通过
  ``memory-backend-file`` 映射客户机内存，gem5 映射同一文件并定位 VRAM 区域。

overlay
  会话目录中为每台机器生成的 qcow2 磁盘层。只读或共享镜像通过 overlay 写入，
  会话结束后与其他会话资源一起删除。

verdict
  会话结束时写入 ``verdict.json`` 的结果记录，包含各进程状态、
  ``users_stopped`` 等字段；最后一行 ``[COSIM_VERDICT]`` 重复该内容。

接口与硬件
----------

vfio-user
  在 Unix socket 之上导出 PCI 设备的协议。vHost 侧由 QEMU 的
  ``vfio-user-pci`` 客户端使用，设备侧由 libvfio-user（gem5 的
  ``MI300XVfioUser``，或 QEMU 的 ``x-vfio-user-server``）提供服务。

BAR
  PCI Base Address Register。MI300X 的布局为：BAR0 与 BAR1 映射 VRAM，BAR2 与
  BAR3 映射 2 MiB Doorbell，BAR4 提供 256 个 MSI-X 向量（8 KiB 表），BAR5 映射
  512 KiB MMIO 寄存器。

MSI-X
  PCI 中断机制。设备通过 IRQ eventfd 通知 vHost，vHost 再把中断注入客户机。

DMA 映射
  vfio-user 的 DMA_MAP 操作，携带文件描述符和文件偏移，让设备访问客户机内存。
  QEMU 与设备进程通过同一共享内存文件交换数据。

GART
  Graphics Address Remapping Table，VMID 0 使用的单级 GPU 页表。每个页表项占
  8 字节；联合仿真模式下页表位于共享 VRAM，gem5 在哈希表未命中时直接从共享 VRAM
  读取页表项。

PM4
  AMD GPU 的命令处理器接口。客户机驱动把 PM4 命令写入队列，gem5 的
  ``PM4PacketProcessor`` 解析并执行。

SDMA
  System DMA 引擎，负责内存拷贝和部分命令处理。gem5 的 ``SDMAEngine`` 对其
  行为建模。

IH
  Interrupt Handler。设备把中断记录写入共享内存中的 IH 记录，更新写指针，再通过
  IRQ eventfd 通知 vHost。

gfx942
  MI300X 的 GPU 架构标识，``rocminfo`` 以该名称报告 agent；HIP 编译使用
  ``--offload-arch=gfx942``。

仿真与构建
----------

gem5
  性能仿真器。本项目的 MI300X 模型运行 PM4、SDMA、Shader/CU、Ruby 内存层次等
  组件，通过 vfio-user 把 GPU 提供给 QEMU 客户机。

QEMU
  功能仿真与虚拟化组件。作为 vHost 时运行客户机 Linux；作为 device model 时通过
  ``x-remote`` 和 ``x-vfio-user-server`` 提供 PCI 设备。

StubWorkload
  gem5 联合仿真配置中使用的工作负载，使设备模型在没有完整 CPU 负载的情况下执行。

SST
  Structural Simulation Toolkit。仓库中的 ``configs/sst/`` 保存多节点网络与
  MI300X 集成实验配置，属于独立的实验路径。

XGMI
  GPU 之间的互联接口。gem5 的 ``XGMIBridge`` 及相关配置实现模拟器内部的互联
  行为；YAML 适配器为每个进程启动一个 GPU。

cluster
  多台机器组成的拓扑组合，``resources/clusters/`` 中的样例通过
  ``count`` 展开机器数量。cluster 是拓扑组合，不是机器目录中的单个 machine。

adapter
  设备启动方式的抽象，取值为适配器 enum（``gem5-mi300x``、
  ``qemu-device`` 或自定义 kind）。适配器定义命令、就绪探测和可挂载设备数量。

相关页面
--------

- :ref:`arch-index`
- :ref:`ref-topology-schema`
- :ref:`topo-index`

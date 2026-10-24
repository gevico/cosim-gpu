.. SPDX-License-Identifier: Apache-2.0

.. _arch-design-decisions:

关键设计取舍
============

本页解释系统为什么把 QEMU 与 gem5 分工、为什么用 vfio-user 连接、为什么用
共享内存池和 Rust launcher，以及这些选择带来的限制。

功能仿真与性能仿真的分工
------------------------

**QEMU 负责功能仿真。** host QEMU 用 KVM（或 TCG）运行真实 Linux 客户机，
完成 PCIe 枚举、amdgpu 驱动加载和 ROCm 程序执行；设备 QEMU 进程则提供正确
的 PCI 寄存器与中断行为。功能仿真回答“程序是否正确”，不回答“有多快”。

**gem5 负责性能仿真。** MI300X 的命令处理器、Shader/CU、缓存与内存层次、
SDMA 和中断路径在 gem5 中按时序建模。性能仿真回答“耗时与瓶颈在哪里”，
不必重新实现一整台可启动的服务器。

**vfio-user 是两者之间的桥。** 它把 PCI 配置空间、BAR、DMA 与中断变成标准
协议，让 QEMU 的功能世界与 gem5 的性能世界可以组合，而 QEMU 不需要知道
对端是 gem5 还是另一个 QEMU 进程。

为什么用 vfio-user 连接
-----------------------

- QEMU 自带 ``vfio-user-pci`` 客户端与 ``x-vfio-user-server`` 服务端，采用
  标准协议就不需要维护 QEMU 补丁；``qemu`` 子模块跟踪的是干净的发布分支。
- 设备模型可以被替换：MI300X 用 gem5，``edu`` 用 QEMU，二者对 host 来说
  都是 vfio-user 设备。
- Unix socket 上完成控制面，数据面使用 fd 与 mmap，避免在 host 与设备进程
  之间复制大块数据。
- 代价是 host 与设备必须同机运行；协议不提供跨网络传输。

为什么用共享内存池
------------------

- VRAM 需要被 QEMU 通过 BAR0 映射，同时被 gem5 当作设备内存访问，文件映射
  是同时满足两者的简单方式。
- 每台机器一个池文件，客户机内存与设备区域在一次布局中确定偏移，避免区域
  重叠与运行期协商。
- 启动前预留容量，容量不足在准备阶段失败，而不是运行到一半才暴露。
- 共享文件只提供存储；缓存与访问顺序由设备模型和客户机软件负责，
  VRAM 访问因此不经过 vfio-user。

为什么用 Rust launcher
----------------------

- 拓扑校验是强类型的：未知字段、重复引用、越界数量都在启动前报错，并能
  导出 JSON Schema。
- 计划可以先预演：``cosim run --dry-run`` 打印程序、参数、环境、探测、内存与磁盘目标，
  便于在真正启动前审查。
- 进程监督与资源所有权明确：进程组、父进程死亡信号、设备租约、镜像租约、
  verdict 与 ``clean`` 都在一个运行时里实现。
- 项目 crate 继承 ``unsafe_code = forbid``；拓扑、运行时与 CLI 分成三个 crate，
  便于替换或扩展。
- 遗留 shell launcher 仍保留给旧流程，详细说明见
  :ref:`遗留 shell launcher <launcher-legacy>`。

为什么由机器直接拥有 vHost
---------------------------------

机器是实际运行单元：它组合一个 vHost 和与之连接的设备模型。因此镜像、内核
命令行和磁盘直接属于该机器的 vHost。这样每台机器的启动选择都明确可见，也不必
再为第二种文档定义生命周期和作用域规则。

代价与限制
----------

- host 与设备必须位于同一系统，不能把设备模型放到另一台机器；
- 没有机器之间的网络、xGMI 或交换机模型；远程 placement 会被本地执行器
  拒绝；
- QEMU 设备模型只保证功能正确，不提供时序；需要时序时使用 gem5 模型；
- YAML 路径为每个 gem5 进程启动一个 GPU，进程内多 GPU 模式不由该路径使用；
- 内存池按完整布局预留，超大机器需要相应的共享内存文件系统容量；
- 随附客户机镜像只面向 x86_64，没有 AArch64 客户机镜像。

相关页面
--------

- :doc:`components`
- :doc:`vfio_user`
- :doc:`memory_model`
- :ref:`Cosim Launcher 介绍 <launcher-index>`
- :ref:`遗留 shell launcher <launcher-legacy>`

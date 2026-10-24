.. SPDX-License-Identifier: Apache-2.0

.. _arch-vfio-user:

vfio-user 通信接口
==================

vfio-user 是 host QEMU 与设备模型之间的桥。QEMU 侧使用内置客户端，设备侧
提供 vfio-user 服务端；协议运行在 Unix socket 上，数据面通过文件描述符与
共享映射完成。

角色
----

.. list-table::
   :header-rows: 1

   * - 角色
     - 实现
     - 说明
   * - host 客户端
     - QEMU ``vfio-user-pci``
     - 在 host 机器上为每个设备创建一个客户端，连接设备 socket
   * - gem5 服务端
     - ``MI300XVfioUser``
     - 基于 libvfio-user，提供 MI300X 配置空间、BAR、DMA 与中断
   * - QEMU 服务端
     - ``x-vfio-user-server``
     - 设备 QEMU 进程导出 ``edu`` 等 PCI 设备的功能模型
   * - 运行管理
     - ``cosim-runtime``
     - 生成 socket 路径、控制启动顺序、探测就绪并在结束时删除 socket

连接与生命周期
--------------

- 每个设备有独立的 Unix socket，位于会话目录的机器子目录下，例如
  ``<run-dir>/<machine>/<device>.sock``；
- Unix socket 与共享文件映射要求 host 与设备进程在同一系统运行，不支持网络
  传输；
- QEMU vHost 命令由 vHost 模板渲染：为每个设备创建 PCIe root port 与
  ``vfio-user-pci`` 客户端，参数包含 socket 路径与可选的 ``romfile``；
- 设备先启动，通过监听日志与 socket 存在两项探测后 host 才启动；会话结束时
  先停 host，再停设备，最后删除 socket；
- vfio-user 上下文完成初始化前必须注册设备能力；PCIe root port 在插槽
  ``0x10`` 到 ``0x17`` 上为设备预留位置。

协议操作
--------

.. list-table::
   :header-rows: 1

   * - 操作
     - 接口
     - 用途
   * - PCI 配置空间与 MMIO
     - vfio-user 消息
     - 枚举设备、读写寄存器
   * - Doorbell 访问
     - 设备 BAR 回调
     - 客户机写 doorbell，触发设备侧工作
   * - 客户机内存共享
     - 携带 fd 与偏移的 ``DMA_MAP``
     - 设备模型访问客户机内存
   * - 可映射 BAR 区域
     - 区域 fd 与 mmap 偏移
     - QEMU 映射 VRAM 等大区域
   * - MSI-X 中断
     - IRQ eventfd 注册与通知
     - 设备向客户机注入中断

MI300X 的 BAR 布局（VRAM、Doorbell、MSI-X 与 MMIO）见
:ref:`MI300X PCI 接口 <sim-gem5-pci>`。

一次 Doorbell 到中断
--------------------

.. mermaid::

   sequenceDiagram
       participant G as 客户机驱动
       participant H as Host QEMU
       participant D as 设备模型
       participant M as 共享内存池
       G->>M: 写命令队列与描述符
       G->>H: 写 Doorbell BAR
       H->>D: vfio-user 消息
       D->>M: 读取命令并执行 DMA
       D->>H: 通知 IRQ eventfd
       H->>G: 注入 MSI-X 中断
       G->>M: 读取完成标记与 IH 记录

中断处理器把 IH 记录写入共享客户机内存，更新写指针，再通过设备模型触发
注册的 eventfd；使用 KVM 时，QEMU 把该通知转换为向客户机注入中断。

DMA 映射
--------

``DMA_MAP`` 携带客户机内存的文件描述符与文件偏移，设备模型据此把客户机
物理地址翻译成自己对共享文件的访问。这样设备不需要复制整段客户机内存，
也不依赖 QEMU 转发每次 DMA。客户机内存的池布局与偏移见
:doc:`memory_model`。

为什么使用 vfio-user
--------------------

使用上游标准协议意味着 QEMU 侧保持未修改的 ``vfio-user-pci``，设备实现只
需要实现协议；共享内存、DMA 与中断都由标准操作表达。取舍分析见
:doc:`design_decisions`。

相关页面
--------

- :doc:`design_decisions`
- :doc:`memory_model`
- :ref:`QEMU 作为 device model <sim-qemu-device-models>`
- :ref:`MI300X PCI 接口 <sim-gem5-pci>`
- :ref:`遗留 shell launcher <launcher-legacy>`

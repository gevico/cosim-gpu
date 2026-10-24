.. SPDX-License-Identifier: Apache-2.0


.. _topo-devices:

设备目录
========

设备是通过 vfio-user 导出给 QEMU 主机的 PCI 模型。本页列出设备种类与配置事实；PCI/BAR 接口、模型覆盖范围与客户机驱动要求在第 4 章详述，设备适配器契约在 :ref:`ref-device-adapters`\ 。

设备种类
--------

.. list-table::
   :header-rows: 1

   * - 设备
     - kind
     - 说明
     - 模型细节
   * - ``mi300x``
     - ``gem5-mi300x``
     - gem5 MI300X 性能模型；每个进程一个 GPU
     - :ref:`sim-gem5-pci`\ 、:ref:`sim-gem5-model`
   * - ``qemu-edu``
     - ``qemu-device``
     - QEMU ``edu`` 功能设备；验证 vfio-user 路径与 option ROM
     - :ref:`sim-qemu-device-models`
   * - 声明的 device kind
     - ``kinds`` 中的 ``role: device``
     - 自定义 ``argv`` 或 ``command`` 的扩展点；仓库样例尚未使用
     - :ref:`ref-device-adapters`

- ``resources/devices/gpu/mi300x.yaml`` 提供 ``mi300x`` 与 ``mi300x-aarch64`` 两个模板；后者只覆盖 gem5 二进制。
- ``resources/devices/pci/qemu-edu.yaml`` 提供 ``qemu-edu`` 与 ``qemu-edu-aarch64`` 两个模板；前者需要带 vfio-user 支持的 QEMU。

设备字段
--------

.. list-table::
   :header-rows: 1

   * - 字段
     - 必需
     - 说明
   * - ``kind``
     - 是
     - 内置 ``gem5-mi300x``\ 、``qemu-device``\ ，或 ``kinds`` 中声明的 device kind
   * - ``id``
     - 否
     - 默认由 ``use`` 名称或 kind 加序号组成；显式 id 在 count 为 1 时保留
   * - ``use``\ 、``count``
     - 否
     - 选择模板；count 把一个条目展开为多个设备进程
   * - ``config``
     - gem5-mi300x 必需
     - gem5 配置文件；``qemu-device`` 拒绝该字段
   * - ``runtime.binary``
     - 除 gem5-mi300x 外必需
     - gem5-mi300x 默认使用 ``gem5.opt``\ ；裸名从 ``PATH`` 查找
   * - ``runtime.argv``\ 、``runtime.command``
     - 否
     - 覆盖适配器命令；这类命令需要 ``ready_log``
   * - ``memory_regions``
     - gem5-mi300x 必需
     - 恰好一个名为 ``vram`` 的区域，大小为 2 的幂；``qemu-device`` 拒绝私有区域
   * - ``pci``
     - 否
     - vendor_id、device_id、msix_vectors 与 rom；MI300X 给定时必须与硬件一致
   * - ``args``
     - 否
     - 适配器参数，见 :ref:`ref-device-adapters`
   * - ``guest_hints``
     - 否
     - modprobe 参数与 cmdline 提示；cmdline 要求 vHost 声明镜像或内核
   * - ``pci.rom``
     - 否
     - host 侧 option ROM，作为 vfio-user 客户端的 romfile 暴露

启动与就绪约定
--------------

- 内置适配器 ``gem5-mi300x`` 与 ``qemu-device`` 各自生成启动命令；声明的 device kind 提供 ``argv`` 或 ``command``\ 。
- 每个设备进程先于主机启动。就绪探测按顺序进行：输出日志标记（``ready_log``\ ，gem5 默认是 MI300X 的监听行）、socket 存在、QMP 协商（``qemu-device``\ ）。
- 设备就绪后向每个依赖它的主机会交出租约；主机停止并释放租约后，最后一个租约释放时设备退出。
- 每个设备程序必须在前台运行、把资源使用者保留在自己的进程组中并保持继承的文件描述符打开。
- ``pci.rom`` 由主机模板作为 vfio-user 客户端的 ``romfile`` 传入，客户机可通过设备 ROM BAR 读取；launcher 在分配会话资源前检查文件是否存在。

设备与内存池
------------

- 设备区域按声明顺序追加在客户机 RAM 之后。区域全名由设备 id 与区域名组成，例如 ``mi300x-0.vram``\ 。
- MI300X 默认 16 GiB VRAM，``gpu-8`` 把每个设备覆盖为 8 GiB；``qemu-edu`` 没有私有区域。
- 区域大小、偏移与对齐写入会话目录的 ``layout.json``\ ；池计算方法见 :doc:`../single_machine`\ 。

如何选择设备
------------

- 需要 GPU 性能模型与 ``amdgpu`` 驱动路径：使用 ``gem5-mi300x``\ ，样例见 :doc:`../machines/single_gpu` 与 :doc:`../machines/gpu_8`\ 。
- 需要验证 vfio-user 设备链路或 option ROM：使用 ``qemu-device`` 的 ``edu``\ ，样例见 :doc:`../machines/qemu_device`\ 。
- 需要自定义启动命令：声明 device kind 并提供 ``ready_log``\ ；仓库样例尚未使用该路径，契约见 :ref:`ref-device-adapters`\ 。
- 模型细节统一看第 4 章：PCI/BAR 见 :ref:`sim-gem5-pci`\ ，性能模型见 :ref:`sim-gem5-model`\ ，QEMU 功能设备见 :ref:`sim-qemu-device-models`\ ，驱动要求见 :ref:`sim-guest-driver`\ 。

相关页面
--------

- 机器目录：:doc:`../machines/index`
- vHost 配置：:doc:`../hosts/index`
- 编写拓扑：:doc:`../write_topology`
- 适配器契约：:ref:`ref-device-adapters`
- 源码：``resources/devices/gpu/mi300x.yaml``\ 、``resources/devices/pci/qemu-edu.yaml``\ 、``crates/cosim-topology/src/adapter/``

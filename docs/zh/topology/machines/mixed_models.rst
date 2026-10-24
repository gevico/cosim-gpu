.. SPDX-License-Identifier: Apache-2.0


.. _topo-machines-mixed-models:

mixed-models 机器
=================

概述
----

``mixed-models`` 在一台机器里同时使用两类设备适配器：2 个 gem5 MI300X 性能模型和 2 个通过 vfio-user 导出的 QEMU ``edu`` 功能设备，共用一个 40 GiB 内存池。它用来说明同一台机器可以组合不同来源的 PCI 设备。

拓扑
----

.. code-block:: yaml

   # resources/machines/mixed-models.yaml
   version: 1
   imports:
     - vhosts/qemu.yaml
     - devices/gpu/mi300x.yaml
     - devices/pci/qemu-edu.yaml
   machines:
     - id: m0
       vhost: {use: vhost-x86}
       devices:
         - {use: mi300x, count: 2}
         - {use: qemu-edu, count: 2}

- 机器数量：1（``m0``\ ）；主机使用默认 ``vhost-x86``\ 。
- 设备标识符：``mi300x-0``\ 、``mi300x-1``\ 、``qemu-edu-0``\ 、``qemu-edu-1``\ 。
- ``qemu-edu`` 不声明私有内存区域；内存池只累加 2 × 16 GiB 的 VRAM。

硬件资源
--------

.. list-table::
   :header-rows: 1

   * - 资源
     - 值
     - 来源
   * - 机器
     - 1 台（``m0``\ ）
     - ``resources/machines/mixed-models.yaml``
   * - vHost 配置
     - ``vhost-x86``\ ：``q35``\ 、``kvm``\ 、8 GiB RAM、4 vCPU
     - ``resources/vhosts/qemu.yaml``
   * - gem5 设备
     - 2 × ``mi300x``\ ，各 16 GiB VRAM、40 CU
     - ``resources/devices/gpu/mi300x.yaml``
   * - QEMU 设备
     - 2 × ``qemu-edu``\ ，``args.device`` 为 ``{driver: edu}``
     - ``resources/devices/pci/qemu-edu.yaml``
   * - 内存池
     - 40 GiB = 8 GiB RAM + 32 GiB VRAM
     - ``crates/cosim-topology/src/layout.rs``
   * - 区域偏移
     - ``mi300x-0.vram`` 位于 8 GiB；``mi300x-1.vram`` 位于 24 GiB
     - 声明顺序
   * - 进程
     - 1 个主机进程 + 2 个 gem5 进程 + 2 个 QEMU 设备进程
     - 会话计划

软件栈
------

.. list-table::
   :header-rows: 1

   * - 层
     - 组件
     - 说明
   * - 客户机 OS
     - Ubuntu 24.04.2 LTS，内核 6.8.0-124-generic
     - 可选 vHost；不启动客户机时只验证硬件与进程组合
   * - GPU 驱动
     - ``amdgpu``\ ，固定参数
     - 只作用于 gem5 MI300X 设备
   * - 功能设备
     - QEMU ``edu``
     - 测试用 PCI 设备，客户机内没有对应驱动
   * - 设备模型
     - gem5 性能模型 + QEMU 功能模型
     - QEMU 设备以 ``-machine x-remote`` 与 ``x-vfio-user-server`` 启动
   * - 客户机初始化
     - ``cosim-gpu-initialize.service``
     - 只处理 AMD PCI 设备

运行该机器
----------

.. code-block:: bash

   # 校验与预览
   just run-cli validate resources/machines/mixed-models.yaml  --assets
   just run-topology resources/machines/mixed-models.yaml --dry-run
   # 启动会话
   just run-topology resources/machines/mixed-models.yaml

- QEMU 设备进程需要由 ``just build-qemu`` 构建的、带 vfio-user 支持的 QEMU。
- 主机在全部 4 个设备就绪并交出租约后才启动；关闭时主机先停止，设备随后退出。
- 生命周期与就绪探测见 :ref:`launcher-session-lifecycle`\ 。

验证
----

- 计划输出为 1 个主机进程与 4 个设备进程，内存池 40 GiB，4 个 vfio-user socket。
- 样例由 render 测试加载；MI300X 模型与 vfio-user 设备路径分别有独立的测试作业。
- 这个由两种适配器组成的样例本身没有专门的 CI 作业端到端覆盖。

限制
----

- 两个适配器分别有测试，但本组合的端到端客户机行为以本地运行为准。
- ``qemu-edu`` 是测试设备，不提供客户机驱动；客户机只会看到未绑定驱动的 PCI 设备。
- 运行需要 Linux glibc 与 ``setpriv``\ ；客户机启动需要 KVM。
- 40 GiB 内存池加 4 个设备进程，运行前确认主机内存与 ``/dev/shm`` 容量。

相关页面
--------

- 设备目录：:doc:`../devices/index`
- vHost 配置：:doc:`../hosts/index`
- vHost：:ref:`ref-topology-schema`
- 机器目录：:doc:`index`
- 第 4 章：:ref:`sim-gem5-model`\ ，:ref:`sim-qemu-device-models`
- 源码：``resources/machines/mixed-models.yaml``\ 、``resources/devices/gpu/mi300x.yaml``\ 、``resources/devices/pci/qemu-edu.yaml``

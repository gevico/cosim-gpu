.. SPDX-License-Identifier: Apache-2.0


.. _topo-machines-gpu-8:

gpu-8 机器
==========

概述
----

``gpu-8`` 是单机多 GPU 板卡：一台 ``vhost-x86`` 主机带 8 个 gem5 MI300X 设备，每个设备 8 GiB VRAM，共享一个 96 GiB 内存池。它用来观察单机的设备进程扇出与内存池容量计算。

拓扑
----

.. code-block:: yaml

   # resources/machines/gpu-8.yaml
   version: 1
   imports:
     - vhosts/qemu.yaml
     - devices/gpu/mi300x.yaml
   templates:
     node8:
       vhost:
         use: vhost-x86
         memory: 32G
         cpus: 16
       devices:
         - use: mi300x
           count: 8
           memory_regions:
             - {name: vram, size: 8G, align: 2M}
   machines:
     - {id: m0, use: node8}

- 机器数量：1（``m0``\ ）；``node8`` 模板同时被集群样例复用，见 :doc:`../multi_machine`\ 。
- ``count: 8`` 把设备标识符展开为 ``mi300x-0`` 到 ``mi300x-7``\ 。
- 每个设备区域为 8 GiB、对齐 2 MiB；客户机 RAM 为 32 GiB。

硬件资源
--------

.. list-table::
   :header-rows: 1

   * - 资源
     - 值
     - 来源
   * - 机器
     - 1 台（``m0``\ ）
     - ``resources/machines/gpu-8.yaml``
   * - vHost 配置
     - ``vhost-x86``\ ：``q35``\ 、``kvm``\ 、16 vCPU
     - ``resources/vhosts/qemu.yaml``
   * - 客户机 RAM
     - 32 GiB
     - ``gpu-8.yaml``
   * - 设备
     - 8 × ``mi300x``\ ，各 8 GiB VRAM、40 CU
     - ``resources/devices/gpu/mi300x.yaml``
   * - 内存池
     - 96 GiB = 32 GiB RAM + 64 GiB VRAM
     - ``crates/cosim-topology/src/layout.rs``
   * - 区域偏移
     - ``mi300x-0.vram`` 位于 32 GiB；``mi300x-7.vram`` 位于 88 GiB
     - 声明顺序
   * - 进程
     - 1 个主机进程 + 8 个 gem5 进程
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
     - 可选 vHost；板卡本身只描述硬件
   * - GPU 驱动
     - ``amdgpu``\ ，固定参数
     - ``ip_block_mask=0x67 ppfeaturemask=0 dpm=0 audio=0 ras_enable=0 discovery=2``
   * - 设备模型
     - 8 个独立 gem5 MI300X 进程
     - 每个进程一个 GPU（``--num-gpus=1``\ ）
   * - 客户机初始化
     - ``cosim-gpu-initialize.service``
     - 对每个模拟设备执行 ROM ``dd`` 与 ``modprobe``

运行该机器
----------

.. code-block:: bash

   # 校验并预览 96 GiB 内存池的布局
   just run-cli validate resources/machines/gpu-8.yaml  --assets
   just run-topology resources/machines/gpu-8.yaml --dry-run
   # 启动会话
   just run-topology resources/machines/gpu-8.yaml

- 内存池目录需要有 96 GiB 可用空间；Linux 上默认位于 ``/dev/shm`` 下。
- 关闭流程与单机相同：主机退出后设备依次停止；生命周期见 :ref:`launcher-session-lifecycle`\ 。

验证
----

- 计划输出中有 1 个主机进程与 8 个设备进程，内存池 96 GiB；``layout.json`` 记录每个区域偏移。
- 样例由 render 测试加载；模型与内存池另由 ``just test-gem5-mi300x`` 检查。
- 仓库内没有覆盖完整 8 进程客户机运行的 CI 作业；多 GPU 客户机行为以本地运行为准。

限制
----

- 96 GiB 内存池加上 8 个 gem5 进程占用较高，运行前先确认内存与 ``/dev/shm`` 容量。
- YAML 适配器每个进程一个 GPU；YAML 中无法启用 gem5 的进程内多 GPU 模式。
- 8 个 GPU 之间没有 XGMI 或卡间 fabric 模型；多 GPU 与 XGMI 的事实边界见 :ref:`sim-gem5-multi-gpu`\ 。
- 启动客户机需要 KVM；运行会话需要 Linux glibc 与 ``setpriv``\ 。

相关页面
--------

- 单机拓扑与内存池算术：:doc:`../single_machine`
- vHost 配置：:doc:`../hosts/index`
- 设备目录：:doc:`../devices/index`
- vHost：:ref:`ref-topology-schema`
- 机器目录：:doc:`index`
- 第 4 章：:ref:`sim-gem5-model`\ ，:ref:`sim-gem5-multi-gpu`
- 源码：``resources/machines/gpu-8.yaml``\ 、``resources/devices/gpu/mi300x.yaml``

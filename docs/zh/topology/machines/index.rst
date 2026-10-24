.. SPDX-License-Identifier: Apache-2.0


.. _topo-machines-index:

机器目录
========

一台机器（板卡）固定一组组合：一个 vHost、一组设备，以及由二者推导的内存池。
本页只列 ``resources/machines/`` 下的单机板卡。

目录表
------

.. list-table::
   :header-rows: 1

   * - 机器
     - vHost 配置
     - 设备与内存池
     - 备注
   * - :doc:`single-gpu <single_gpu>`
     - ``vhost-x86``\ （Q35、KVM），8 GiB RAM、4 vCPU
     - 1 × ``mi300x`` 16 GiB VRAM；24 GiB 池
     - 标准单 GPU 客户机板卡；快速开始示例
   * - :doc:`gpu-8 <gpu_8>`
     - ``vhost-x86``\ ，32 GiB RAM、16 vCPU
     - 8 × ``mi300x`` 8 GiB VRAM；96 GiB 池
     - 单机多 GPU 与内存池容量示例
   * - :doc:`mixed-models <mixed_models>`
     - ``vhost-x86``\ ，8 GiB RAM、4 vCPU
     - 2 × ``mi300x`` + 2 × ``qemu-edu``\ ；40 GiB 池
     - gem5 与 QEMU 设备模型同机组合
   * - :doc:`host-only <host_only>`
     - ``vhost-x86-tcg``\ （暂停），64 MiB RAM、1 vCPU
     - 无设备；64 MiB 池
     - 无客户机的 QEMU、内存与 QMP 管理
   * - :doc:`qemu-device <qemu_device>`
     - ``vhost-x86-tcg``\ （暂停），64 MiB RAM、1 vCPU
     - 1 × ``qemu-edu``\ ；64 MiB 池
     - vfio-user 设备路径与 option ROM
   * - :doc:`aarch64 <aarch64>`\ （host-only-aarch64）
     - ``vhost-arm-tcg``\ （暂停），64 MiB RAM、1 vCPU
     - 无设备；64 MiB 池
     - AArch64 主机基础链路
   * - :doc:`aarch64 <aarch64>`\ （gem5-aarch64）
     - ``vhost-arm-tcg``\ ，512 MiB RAM、1 vCPU
     - 1 × ``mi300x-aarch64`` 1 GiB VRAM；1.5 GiB 池
     - 原生 ARM64 gem5 构建；没有 AArch64 客户机镜像
   * - :doc:`aarch64 <aarch64>`\ （qemu-device-aarch64）
     - ``vhost-arm-tcg``\ （暂停），64 MiB RAM、1 vCPU
     - 1 × ``qemu-edu-aarch64``\ ；64 MiB 池
     - 依赖 AArch64 QEMU 构建

板卡页面
--------

.. toctree::
   :maxdepth: 1

   single_gpu
   gpu_8
   mixed_models
   host_only
   qemu_device
   aarch64

如何阅读一行
------------

- vHost 配置：定义在 ``resources/vhosts/``\ ，profile 说明见 :doc:`../hosts/index`\ 。
- 设备：经 vfio-user 导出的模型，种类与字段见 :doc:`../devices/index`\ 。
- 设备与内存池：池大小等于客户机 RAM 加设备区域，计算方式见 :doc:`../single_machine`\ 。
- 备注：只写事实，例如设备组合、是否有客户机镜像、依赖哪个构建产物。
- AArch64 三行共用系列页 :doc:`aarch64`\ 。

推荐阅读路径
------------

- 第一次运行客户机：:doc:`single_gpu`
- 需要更多 GPU：:doc:`gpu_8`
- 同时使用 gem5 与 QEMU 设备模型：:doc:`mixed_models`
- 只测试会话生命周期：:doc:`host_only`
- 测试 vfio-user 设备：:doc:`qemu_device`
- AArch64 主机链路：:doc:`aarch64`

源码与证据
----------

- 机器样例：``resources/machines/``\ 。
- 集群样例（不属于板卡层）：``resources/clusters/``\ ，说明见 :doc:`../multi_machine`\ 。
- 全部样例由 ``crates/cosim-topology/tests/topology.rs`` 的 render 测试加载。

相关页面
--------

- 拓扑层：:doc:`../single_machine`\ 、:doc:`../multi_machine`
- 组件：:doc:`../hosts/index`\ 、:doc:`../devices/index`\ 、:ref:`ref-topology-schema`
- 编写拓扑：:doc:`../write_topology`

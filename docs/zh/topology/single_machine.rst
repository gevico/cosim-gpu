.. SPDX-License-Identifier: Apache-2.0


.. _topo-single-machine:

单机拓扑
========

单机拓扑只声明一台机器：一个 QEMU 主机、连接到它的设备进程，以及一个共享内存池。本页说明单机如何组合、进程如何排布、内存池如何计算；可以直接运行的样例见机器目录。

单机的组成
----------

.. list-table::
   :header-rows: 1

   * - 部分
     - 作用
     - 在 YAML 中的写法
   * - 机器
     - 一次会话中的一台独立主机
     - ``machines`` 列表中的一项，带 ``id``
   * - 主机
     - 运行客户机的 QEMU；绑定内存池，提供 QMP、串口与 PCIe 根端口
     - ``vhost.use`` 选择 vHost 模板，可覆盖镜像、启动、``memory``\ 、``cpus`` 等字段
   * - 设备
     - 通过 vfio-user 导出给主机的 PCI 设备
     - ``devices`` 列表中的 ``use`` 或 ``kind``\ ，以及 ``count``
   * - 内存池
     - 每台机器一个文件：客户机 RAM 加各设备内存区域
     - 由主机 ``memory`` 与设备 ``memory_regions`` 推导，不单独声明

.. mermaid::

   flowchart LR
       Y[单机 YAML] --> H[QEMU 主机]
       H --- P[(内存池)]
       D0[设备 0] -->|vfio-user| H
       D1[设备 N] -->|vfio-user| H
       D0 --- P
       D1 --- P

进程扇出
--------

- 一台机器固定有一个主机进程；每个设备是一个独立进程，``count: 8`` 会得到 8 个设备进程。
- gem5 MI300X 适配器每个进程只启动一个 GPU（``--num-gpus=1``\ ）；GPU 数量通过设备数量扩展。
- 设备先于主机启动：设备就绪后向依赖它的主机交出租约，主机停止后释放租约，最后一个租约释放后设备才退出。
- 单机内部没有跨机器等待；同一文档中的多台机器各自独立，见 :doc:`multi_machine`\ 。

内存池计算
----------

内存池大小等于客户机 RAM 加上全部设备区域：

.. list-table::
   :header-rows: 1

   * - 拓扑
     - 客户机 RAM
     - 设备区域
     - 内存池
   * - ``single-gpu``
     - 8 GiB
     - 16 GiB（``mi300x`` 默认）
     - 24 GiB
   * - ``gpu-8``
     - 32 GiB
     - 8 × 8 GiB = 64 GiB
     - 96 GiB
   * - ``mixed-models``
     - 8 GiB
     - 2 × 16 GiB = 32 GiB（``qemu-edu`` 无私有区域）
     - 40 GiB
   * - ``gem5-aarch64``
     - 512 MiB
     - 1 GiB
     - 1.5 GiB

- 客户机 RAM 位于内存池开头，设备区域按声明顺序追加；``gpu-8`` 的 ``mi300x-0.vram`` 位于 32 GiB，``mi300x-7.vram`` 位于 88 GiB。
- 区域大小可以写成整数或 ``32G`` 这类二进制单位；大小必须是执行系统页大小的整数倍，``align`` 必须是不小于一页的 2 的幂（默认 2 MiB）。
- 每台机器的区域偏移与大小写入会话目录的 ``layout.json``\ ，在生成计划阶段就能检查。

运行目录与资源
--------------

单机同样获得完整的会话资源：每台机器一个运行子目录、一个内存池文件和一份 ``layout.json``\ ；每个设备一个 vfio-user socket，主机另有 QMP 与串口 socket。运行目录默认为 ``.cosim/`` 下的会话目录，Linux 上内存池目录默认为 ``/dev/shm/cosim-<name>-<hash>``\ 。生命周期细节见 :ref:`launcher-session-lifecycle`\ 。

一个最小单机示例
----------------

.. code-block:: yaml

   version: 1
   imports:
     - vhosts/qemu.yaml
     - devices/gpu/mi300x.yaml
   machines:
     - id: m0
       vhost: {use: vhost-x86}
       devices:
         - {use: mi300x}

``resources/machines/single-gpu.yaml`` 用模板复用同样的组合；完整的编写规则见 :doc:`write_topology`\ 。

源码与证据
----------

- 样例：``resources/machines/`` 下的全部机器文件。
- 实现：``crates/cosim-topology/src/layout.rs``\ （内存池布局）、``crates/cosim-runtime/src/layout.rs``\ （会话路径）。
- 命令：``cosim validate``\ 、``cosim run --dry-run``\ 、``cosim graph``\ 。

相关页面
--------

- 拓扑写法：:doc:`write_topology`
- 机器目录：:doc:`machines/index`
- 主机与设备：:doc:`hosts/index`\ ，:doc:`devices/index`
- 内存模型：:ref:`arch-memory-model`

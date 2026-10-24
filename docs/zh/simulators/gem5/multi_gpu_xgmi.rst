.. SPDX-License-Identifier: Apache-2.0

.. _sim-gem5-multi-gpu:

多 GPU、XGMI 与 SST
====================

本页说明多 GPU 的两种存在方式（每进程一个 GPU 的 YAML 路径，以及单 gem5 进程内的多 GPU 路径）、XGMI 桥的当前实现，以及 SST 实验与 launcher 的事实边界。

两种运行模式
-------------

.. list-table::
   :header-rows: 1

   * - 模式
     - 入口
     - 特点
   * - 每进程一个 GPU
     - YAML ``gem5-mi300x``\ 适配器
     - 适配器固定传 ``--num-gpus=1``\ 和 ``--shared-pool``\ ；每个设备进程拥有自己的 vfio-user socket 和 VRAM 区域。
   * - 单进程多 GPU
     - 直接调用 ``gem5.opt``\ 并传 ``--num-gpus N``
     - 每个 GPU 有自己的 ``AMDGPUDevice``\ 、Shader 和 vfio-user 桥；所有 GPU 共享一个 Ruby 缓存层次；使用 ``/dev/shm/mi300x-vram-{i}``\ 形式的共享内存，而不是 pool 文件。

- ``--shared-pool``\ 与多 GPU 互斥：传了 ``--shared-pool``\ 时 ``--num-gpus``\ 必须为 1。
- YAML 中想在一台机器上使用多个 GPU，应声明多个设备（例如 ``count: 8``\ ），launcher 会为每个 GPU 启动一个进程；``resources/machines/gpu-8.yaml``\ 就是这种机器。
- 单进程多 GPU 只存在于 vfio-user 后端；两个 gem5 进程之间没有 XGMI 链路。

XGMI 模型
----------

``XGMIBridge``\ 挂在每个 GPU 的 L2（TCC）出口，把目标地址落在远端 GPU VRAM 范围内的请求通过模拟的 xGMI 链路转发，使用带宽限速、基于 gem5 事件的延迟和信用流控。

.. list-table::
   :header-rows: 1

   * - 属性
     - 默认值
     - 说明
   * - 链路带宽
     - ``128GB/s``
     - 每个 GPU 对之间的单向带宽参数。
   * - 单跳延迟
     - ``100ns``
     - 用 gem5 事件模拟。
   * - 链路数
     - ``16``\ 条 lane
     - ``num_lanes``\ 参数。
   * - 最大链路数
     - ``7``
     - ``max_links``\ 参数。
   * - 流控信用
     - ``32``
     - 每条链路的信用数，取尽后背压。
   * - 拓扑
     - ``mesh``\ 或 ``ring``
     - 由 ``--xgmi-topology``\ 选择，要求 ``--num-gpus``\ 至少为 2。

- 数据包类型包括 ``WriteReq``\ 、``ReadReq``\ 、``ReadResp``\ 和 ``Completion``\ 。
- 远端地址判定使用 ``vram_size_per_gpu``\ 计算每个 GPU 的 VRAM 范围。
- ``xgmi_transport.hh``\ 预留了抽象传输接口：进程内实现使用直接 peer 指针；``IPCTransport``\ 只有骨架和 TODO，SST 传输属于设计中的后续阶段，当前配置不使用。

启动示例
---------

.. code-block:: bash

   # 单进程双 GPU，带 mesh 拓扑的 XGMI 链路（直接调用 gem5，不经过 YAML）
   build/gem5/x86_64/VEGA_X86/gem5.opt \
     third_party/gem5/configs/example/gpufs/mi300_cosim.py \
     --num-gpus=2 --xgmi-topology=mesh \
     --socket-path=/tmp/gem5-mi300x --shmem-path=/mi300x-vram

YAML 路径下，一台机器的多个 GPU 对应多个设备进程；进程间没有 XGMI 模型，跨 GPU 访问由客户机软件和 QEMU PCIe 拓扑决定。

SST 实验
---------

- ``configs/sst/multi_node_topology.py``\ 描述 SST 网络参数；``configs/sst/mi300x_merlin_poc.py``\ 是 SST 集成实验。
- 这些配置依赖相应的 SST 组件，拥有独立于 Rust 进程管理的接口，不由 YAML 拓扑或 ``cosim run``\ 驱动。
- ``placement.agent``\ 可以描述远端放置，但 ``cosim run``\ 在分配资源前拒绝远端放置；交换机节点尚未进入拓扑格式。
- 跨机器 DMA 与机器间 fabric 不在当前 launcher 的模型中。

事实边界
---------

- YAML 适配器每进程一个 GPU，XGMI 与单进程多 GPU 只存在于直接调用 gem5 的路径。
- ``--num-gpus``\ 的 socket 与共享内存使用带 GPU 编号的后缀，便于同一台主机上并行运行多个实例。
- SST 与远程 placement 属于独立实验或预留设计，不是 launcher 的可执行路径。
- 多 GPU 下的 ROM 读取通过系统内存进行，旧式 VGA ROM 窗口只由 GPU 0 解码。

源码与依据
-----------

- 多 GPU 配置：``third_party/gem5/configs/example/gpufs/mi300_cosim.py``\ 。
- XGMI 桥：``third_party/gem5/src/dev/amdgpu/xgmi_bridge.{cc,hh}``\ 、``XGMIBridge.py``\ 。
- 传输接口：``third_party/gem5/src/dev/amdgpu/xgmi_transport.hh``\ 。
- SST 配置：``configs/sst/``\ 。
- 机器样例：``resources/machines/gpu-8.yaml``\ 。

相关页面
---------

- :doc:`index`\ ：gem5 的定位。
- :doc:`mi300x_model`\ ：模型组件与命令路径。
- :ref:`appendix-sst-and-placement`\ ：SST 与远端放置的附录说明。
- :ref:`topo-multi-machine`\ ：多机拓扑与 cluster 样例。
- :ref:`topo-machines-gpu-8`\ ：8 GPU 机器样例。

.. SPDX-License-Identifier: Apache-2.0


.. _topo-multi-machine:

多机拓扑
========

多机拓扑就是在同一文档的 ``machines`` 列表里写多个机器条目，或对同一个条目使用 ``count`` 展开。多机仍然是"多台独立的单机"：每台机器有自己的主机、设备进程、内存池、运行子目录和磁盘 overlay，机器之间没有网络或互连模型。

多机语义
--------

- 每台机器独立选择 vHost、镜像、设备列表和内存池大小。
- 机器之间不互相等待：一台机器的主机以状态 0 退出只结束该机器，其他机器继续运行。
- 机器之间没有 NIC、交换机、XGMI 或跨机器 DMA 模型；多节点网络的数据模型是独立的 SST 实验，见 :ref:`appendix-sst-and-placement`\ 。
- ``placement.agent`` 字段会被解析并保存，但 ``cosim run`` 在创建资源前拒绝远端放置。

count 展开
----------

- ``count`` 把 ``id: m, count: 4`` 展开为 ``m0`` 到 ``m3``\ ；一个拓扑最多 4096 台机器。
- 设备同样支持 ``count``\ ；机器与设备标识符的规则见 :doc:`write_topology`\ 。
- 集群文件只导入机器文件；被导入的文档只贡献模板，只有顶层文档贡献可运行机器。
- ``resources/clusters/`` 下的样例都通过导入 ``resources/machines/`` 中的模板来复用机器定义。

集群样例
--------

.. list-table::
   :header-rows: 1

   * - 样例
     - 机器
     - 组成
     - 备注
   * - ``cluster-4x8.yaml``
     - 4（``m0`` 到 ``m3``\ ）
     - 每台 32 GiB RAM + 8 × 8 GiB VRAM = 96 GiB 池
     - 4 个 KVM 主机 + 32 个 gem5 进程；``cosim graph`` 的示例输入
   * - ``cluster-placed.yaml``
     - 2
     - 每台与 ``cluster-4x8`` 相同
     - 声明 ``placement.agent``\ ；``cosim run`` 拒绝远端放置
   * - ``tcg-pair.yaml``
     - 2（``m0``\ 、``m1``\ ）
     - 每台 ``vhost-x86-tcg``\ ，无设备，64 MiB 池
     - 暂停的 TCG 主机，用于多机会话生命周期
   * - ``tcg-pair-aarch64.yaml``
     - 2（``m0``\ 、``m1``\ ）
     - 每台 ``vhost-arm-tcg``\ ，无设备，64 MiB 池
     - AArch64 版本的同构样例

多机的资源路由
--------------

.. list-table::
   :header-rows: 1

   * - 资源
     - 作用范围
     - 位置
   * - 内存池
     - 每台机器一个
     - ``<pool-dir>/<machine>/pool``\ ；Linux 上默认位于 ``/dev/shm/cosim-<name>-<hash>``
   * - 运行目录
     - 每台机器一个子目录
     - ``.cosim/<name>/<machine>/``\ ，含 ``layout.json``\ 、``plan.json`` 等元数据
   * - vfio-user socket
     - 每个设备一个
     - ``<run>/<machine>/<device>.sock``
   * - 磁盘 overlay
     - 每台机器一份
     - 会话目录中由 vHost 的磁盘声明生成
   * - 磁盘锁
     - 主机共享
     - ``COSIM_DISK_LOCK_DIR``\ ，默认 ``~/.cache/cosim-gpu/disk-locks``

运行多机
--------

.. code-block:: bash

   # 只查看结构，不启动进程
   just run-cli graph resources/clusters/cluster-4x8.yaml
   just run-cli validate resources/clusters/cluster-4x8.yaml
   # 启动多机会话
   just run-topology resources/clusters/tcg-pair.yaml --run-for 5

- ``cosim graph`` 把每台机器渲染为一个 Mermaid 子图，并画出主机与设备的 vfio-user 边。
- 运行前先估算资源：``cluster-4x8`` 需要 4 × 96 GiB 内存池、4 个 QEMU 主机和 32 个 gem5 进程，池目录必须有足够空间。
- 运行约束与单机相同：Linux glibc 与 ``setpriv``\ ，设备先于主机启动、后于主机停止；见 :ref:`launcher-session-lifecycle`\ 。

限制
----

- 没有跨机器 fabric、调度或对等通信实现；本页描述的是"一个会话中的多台独立机器"。
- SST 配置只描述网络拓扑数据模型，不属于本启动器的多机能力，见 :ref:`appendix-sst-and-placement`\ 。
- 每台机器拥有自己的 vHost，可以选择不同的镜像和磁盘。

相关页面
--------

- 单机组合：:doc:`single_machine`
- 机器目录：:doc:`machines/index`
- 会话生命周期：:ref:`launcher-session-lifecycle`
- SST 与 placement：:ref:`appendix-sst-and-placement`

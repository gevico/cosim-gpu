.. SPDX-License-Identifier: Apache-2.0


.. _topo-index:

拓扑结构与硬件支持
==================

本章说明拓扑可以描述哪些机器组合，以及每台机器如何由一个 vHost 和零个或多个
设备模型组成。

三层模型
--------

.. list-table::
   :header-rows: 1

   * - 层
     - 回答的问题
     - 页面
   * - 拓扑族
     - 一个 YAML 文档描述一台还是多台机器？
     - :doc:`single_machine`\ 、:doc:`multi_machine`
   * - 机器（板卡）
     - 哪种"vHost + 设备"组合可以直接运行？
     - :doc:`machines/index`
   * - 组件
     - vHost 与设备模型分别接受什么？
     - :doc:`hosts/index`\ 、:doc:`devices/index`

.. mermaid::

   flowchart TD
       T[拓扑族] --> M[机器 / 板卡]
       M --> H[vHost]
       M --> D[设备]

本章内容
--------

.. toctree::
   :maxdepth: 1

   single_machine
   multi_machine
   write_topology
   machines/index
   hosts/index
   devices/index

推荐阅读路径
------------

- 第一次接触：:doc:`single_machine` → :doc:`machines/index` → :doc:`machines/single_gpu`\ 。
- 要写自己的拓扑：先读 :doc:`write_topology`\ ，再对照 :doc:`machines/index` 中的样例改动。
- 关心多 GPU 或混合设备：:doc:`machines/gpu_8`\ ，:doc:`machines/mixed_models`\ 。
- 要把多台机器放进一个会话：:doc:`multi_machine`\ 。
- 需要主机与设备的完整字段：:doc:`hosts/index`\ 、:doc:`devices/index`\ ，以及 :ref:`ref-topology-schema`\ 、:ref:`ref-device-adapters`\ 。

相关页面
--------

- 首次会话与命令：:ref:`gs-first-session`\ 、:ref:`launcher-cli`
- 内存池与 vfio-user：:ref:`arch-memory-model`\ 、:ref:`arch-vfio-user`
- 设备模型细节：:ref:`sim-qemu-index`\ 、:ref:`sim-gem5-index`

.. SPDX-License-Identifier: Apache-2.0

.. _index:

cosim-gpu 文档
==============

cosim-gpu 用 QEMU 运行真实 Linux 客户机，用 gem5 对 AMD MI300X GPU 做性能仿真，
两者通过 vfio-user 与共享内存协同。本套文档以中文为主，英文版同步维护。

.. grid:: 1 1 2 2
   :gutter: 2

   .. grid-item-card:: 快速开始
      :link: getting_started/index
      :link-type: doc

      从环境准备、构建、客户机镜像到第一次联合仿真。

   .. grid-item-card:: 整体架构
      :link: architecture/index
      :link-type: doc

      组件、执行流程、内存模型与 vfio-user 接口。

   .. grid-item-card:: Cosim Launcher
      :link: launcher/index
      :link-type: doc

      Rust 启动器的命令、YAML 流程、会话生命周期与扩展点。

   .. grid-item-card:: QEMU 与 gem5
      :link: simulators/index
      :link-type: doc

      QEMU 的 vhost 与 device model 功能仿真；gem5 的性能仿真。

   .. grid-item-card:: 拓扑结构与硬件支持
      :link: topology/index
      :link-type: doc

      单机/多机拓扑、machine 目录、host 与 device 支持。

   .. grid-item-card:: 参考与贡献
      :link: reference/index
      :link-type: doc

      schema、参数、版本与已知问题；以及贡献流程。

.. toctree::
   :hidden:
   :maxdepth: 1

   getting_started/index
   architecture/index
   launcher/index
   simulators/index
   topology/index
   reference/index
   contributing/index
   glossary
   appendix/sst_and_placement

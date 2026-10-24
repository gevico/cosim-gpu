.. SPDX-License-Identifier: Apache-2.0

.. _arch-index:

整体架构介绍
============

本章解释系统由哪些部件组成、一次会话如何推进、内存与 vfio-user 如何把 QEMU
与设备模型连接起来，以及这些选择背后的取舍。

本章内容
--------

.. toctree::
   :maxdepth: 1

   components
   execution_flow
   memory_model
   vfio_user
   design_decisions

设计目标
--------

- 用 QEMU 运行真实 Linux 客户机与 ROCm 软件栈，获得可用的 CPU、PCIe 枚举和
  标准设备；
- 用 gem5 对 MI300X 做性能仿真，把时序与微架构研究与功能正确性分开；
- 用 vfio-user 标准协议连接两者，QEMU 侧不需要为联合仿真打补丁；
- 用 YAML 声明机器与设备，执行计划可以预演、监督和清理；
- 用共享内存文件共享客户机内存与 VRAM，避免大块数据拷贝。

推荐阅读路径
------------

- 先了解全貌：:doc:`components` → :doc:`execution_flow`
- 关心数据通路：:doc:`memory_model` → :doc:`vfio_user`
- 关心为什么这样设计：:doc:`design_decisions`
- 需要命令、YAML 与模型细节：第 3、4、5 章

与其他章节的分工
----------------

.. list-table::
   :header-rows: 1

   * - 章节
     - 内容
   * - 快速开始
     - 构建与第一次会话
   * - 本章
     - 组件、执行流程、内存、协议和设计取舍
   * - Cosim Launcher
     - CLI、YAML 流程、会话生命周期与 Rust 工作区
   * - QEMU 与 gem5
     - QEMU vhost/device model 与 gem5 MI300X 模型细节
   * - 拓扑与硬件支持
     - 机器目录、host/device/vHost 与 YAML 编写

相关页面
--------

- :doc:`components`
- :doc:`execution_flow`
- :doc:`memory_model`
- :doc:`design_decisions`
- :ref:`QEMU 与 gem5：功能仿真与性能仿真 <sim-index>`

.. SPDX-License-Identifier: Apache-2.0

.. _gs-next-steps:

下一步
======

跑通第一次会话后，按目标选择后续章节。本页只做导流，不重复各章内容。

理解系统如何工作
----------------

从 :ref:`整体架构介绍 <arch-index>` 开始，先看 :ref:`组件与职责 <arch-components>`
理解 QEMU 功能仿真、gem5 性能仿真与 vfio-user 的分工，再看
:ref:`会话执行流程 <arch-execution-flow>` 与 :ref:`内存与共享内存模型 <arch-memory-model>`。

使用与扩展 launcher
-------------------

命令行、YAML 到计划的转换、会话生命周期和排错见第 3 章：

- :ref:`命令与选项 <launcher-cli>`
- :ref:`YAML 加载、模板与计划 <launcher-yaml-pipeline>`
- :ref:`会话生命周期与资源管理 <launcher-session-lifecycle>`
- :ref:`会话排错 <launcher-debugging-sessions>`

深入仿真器与驱动
----------------

QEMU 作为 vhost 与 device model 的细节、gem5 MI300X 性能模型和客户机驱动
要求见第 4 章：

- :ref:`QEMU 与 gem5：功能仿真与性能仿真 <sim-index>`
- :ref:`MI300X 性能模型 <sim-gem5-model>`
- :ref:`客户机驱动要求 <sim-guest-driver>`

编写自己的拓扑
--------------

机器目录、host 与 device 配置、vHost 以及如何编写拓扑 YAML 见第 5 章：

- :ref:`拓扑结构与硬件支持 <topo-index>`
- :ref:`机器目录 <topo-machines-index>`
- :ref:`如何编写拓扑 YAML <topo-write-topology>`

查表与排错
----------

schema、参数、版本、产物路径与已知问题见第 6 章：

- :ref:`客户机参数 <ref-guest-parameters>`
- :ref:`版本矩阵 <ref-version-matrix>`
- :ref:`产物、路径与源码地图 <ref-files-and-artifacts>`
- :ref:`已知问题 <ref-known-issues>`

相关页面
--------

- :doc:`index`
- :doc:`verify_guest`
- :ref:`整体架构介绍 <arch-index>`
- :ref:`Cosim Launcher 介绍 <launcher-index>`
- :ref:`拓扑结构与硬件支持 <topo-index>`

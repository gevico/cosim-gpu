.. SPDX-License-Identifier: Apache-2.0

.. _launcher-yaml-pipeline:

YAML 加载与计划
================

本页说明拓扑 YAML 如何经过导入、模板合并、校验和内存布局，最终生成本机执行计划。字段语义的完整参考见第 6 章。

流水线概览
-----------

.. mermaid::

   flowchart LR
       Y[顶层 YAML 文档] --> L[导入与模板合并]
       L --> V[校验与标识符展开]
       V --> M[内存布局]
       M --> P[ExecEnv 与 SessionLayout]
       P --> J[plan JSON]

``cosim-topology``\ 只读取 YAML 文档，结果与执行它的系统无关；``cosim-runtime``\ 加入本机事实和会话路径后生成计划，``run``\ 才真正创建资源。

拓扑文档
--------

顶层文档包含 ``version: 1``\ ，以及 ``imports``\ 、``templates``\ 、``kinds``\ 、
``machines``\ 中的任意几项。未知字段会报错。每台机器直接包含自己的 ``vhost``
映射，其中包括镜像、直接启动和存储字段。

.. code-block:: yaml

   version: 1
   imports:
     - vhosts/qemu.yaml
     - devices/gpu/mi300x.yaml
   machines:
     - id: m0
       vhost: {use: vhost-x86, memory: 32G}
       devices:
         - {use: mi300x, count: 2}

导入与模板展开
---------------

- 导入路径先相对导入它的文件解析，再相对 ``--resources``\ 目录（默认 ``resources/``\ ）解析；接受 ``#templates``\ 后缀。
- 被导入的文件提供模板、kind 和进一步的导入；只有顶层文档提供可运行的机器。
- ``use``\ 选择模板。映射递归合并，序列整体替换，显式写出的值覆盖模板值。
- 导入循环、模板循环、重复的模板或 kind 名称以及未知引用都会报错；同一文件经多条路径导入时只加载一次。
- ``resources/``\ 中 ``vhosts/``\ 和 ``devices/``\ 不导入其他文件，``machines/``\ 导入二者，``clusters/``\ 导入 ``machines/``\ 。

校验与标识符
-------------

- 标识符由 1 到 48 个字母、数字、下划线或连字符组成；机器、设备和磁盘标识符不能只在 ASCII 大小写上不同。
- ``count``\ 把 ``id: m, count: 4``\ 展开为 ``m0``\ 到 ``m3``\ ，机器总数最多 4096 台。
- 机器标识符 ``memory``\ ，以及设备标识符 ``vhost``\ 、``qmp``\ 、``serial``\ 由会话布局保留，不能复用。
- 一台机器的设备数量不能超过其 vHost kind 的 ``max_devices``\ （``qemu-vhost``\ 为 64）。
- ``placement.agent``\ 可以描述远端放置，但 ``cosim run``\ 会在分配资源前拒绝执行远端放置。
- 资源路径相对工作区根目录解析，不能包含 ``..``\ ；绝对路径可以使用。不含 ``/``\ 的可执行文件名在生成计划时从 ``PATH``\ 查找。

内存布局
---------

每台机器有一个内存池文件：客户机内存位于开头，设备区域按声明顺序排列。区域大小可以写成整数或 ``32G``\ 这类二进制单位，必须是执行系统页大小的整数倍；对齐边界必须是不小于一页的 2 的幂，默认为 2 MiB。

例如 32 GiB 内存的 host 加上 8 个 8 GiB VRAM 区域时，内存池为 96 GiB，``mi300x-0.vram``\ 位于 32 GiB，``mi300x-7.vram``\ 位于 88 GiB。每台机器的区域名称、偏移和大小写入会话目录的 ``layout.json``\ 。

生成执行计划
-------------

- ``ExecEnv``\ 记录页大小、绝对路径形式的 ``PATH``\ 和磁盘锁目录（``COSIM_DISK_LOCK_DIR``\ ，默认 ``~/.cache/cosim-gpu/disk-locks``\ ）。
- ``SessionLayout``\ 命名所有会话路径：运行目录默认为 ``.cosim/<name>``\ ，Linux 上内存池目录默认为 ``/dev/shm/cosim-<name>-<hash>``\ 。
- 计划记录程序、参数、环境、依赖、就绪探测、共享内存区域、磁盘目标和锁文件路径；进程按“每个设备排在它的 host 之前”排序。
- ``validate``\ 和 ``plan``\ 只做解析与渲染，不启动进程；``run``\ 才会创建运行目录、内存池和磁盘 overlay。
- 设备命令由适配器渲染：``gem5-mi300x``\ 生成 gem5 参数，``qemu-device``\ 生成 QEMU ``x-remote``\ 参数，模板 kind 则按 YAML 命令渲染。

源码与依据
-----------

- 导入、合并与校验：``crates/cosim-topology/src/loader.rs``\ 、``resolve.rs``\ 。
- 内存布局：``crates/cosim-topology/src/layout.rs``\ 。
- 本机环境与计划：``crates/cosim-runtime/src/env.rs``\ 、``layout.rs``\ 、``plan.rs``\ 。
- 设备适配器：``crates/cosim-topology/src/adapter/``\ 。
- 示例：``resources/machines/single-gpu.yaml``\ 、``resources/vhosts/qemu.yaml``\ 。

相关页面
---------

- :doc:`cli`\ ：命令与选项。
- :doc:`session_lifecycle`\ ：计划如何被执行和监督。
- :ref:`topo-write-topology`\ ：如何编写拓扑 YAML。
- :ref:`ref-topology-schema`\ ：字段、类型与默认值。
- :ref:`ref-device-adapters`\ ：设备适配器契约。

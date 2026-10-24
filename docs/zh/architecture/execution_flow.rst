.. SPDX-License-Identifier: Apache-2.0

.. _arch-execution-flow:

会话执行流程
============

一次会话从 YAML 拓扑开始，经过计划生成、资源准备、进程启动与就绪探测，
最后收尾并写入 verdict。本页按这个顺序说明各步骤。

从拓扑到计划
------------

launcher 先加载并校验拓扑：

- 解析 ``imports``、``templates``、``kinds`` 与 ``machines``，展开 ``count``，
  检查标识符、引用与设备数量上限；
- 校验每台机器的 vHost，包括镜像、直接启动字段与磁盘；
- 结合本机事实生成计划：页大小、绝对化 ``PATH``、磁盘锁目录
  （``COSIM_DISK_LOCK_DIR``，默认 ``~/.cache/cosim-gpu/disk-locks``）；
- 渲染每个进程的程序、参数、环境、就绪探测、内存区域、磁盘目标与锁路径。

``cosim run <yaml> --dry-run`` 只打印这份 JSON 计划，不启动任何进程，适合在运行前
检查参数与路径；``cosim graph`` 输出机器与设备连接的 Mermaid 图。

会话启动
--------

.. mermaid::

   sequenceDiagram
       participant L as Launcher
       participant D as 设备进程
       participant H as QEMU vHost
       participant P as 内存池
       L->>P: 预留容量
       L->>D: 启动并探测就绪
       D->>D: 创建 vfio-user socket
       D-->>L: 租约
       L->>H: 持有全部租约后启动
       H-->>L: QMP 就绪
       Note over L,H: 会话运行
       L->>H: 停止 vHost
       H-->>D: 释放租约
       L->>D: 停止设备
       L->>P: 删除内存池

启动顺序是固定的：

1. 以临时名称创建运行目录，写入 ``session.lock``、``plan.json``、
   ``options.json`` 与 ``manifest.json``，再重命名发布；
2. 创建内存池目录并写入所有权标记，为每台机器预留池容量；
3. 准备磁盘：为每台机器创建 qcow2 overlay，或使用其 vHost 声明的只读/直写
   镜像；``create: true`` 时用 ``qemu-img`` 创建缺失镜像；
4. 启动设备进程：独立进程组，``setpriv --pdeathsig KILL`` 随 launcher 结束；
5. 设备通过探测后交出租约，vHost 持有本机全部设备的租约后启动；
6. vHost 完成 QMP 协商，可选等待 ``serial.wait_for`` 标记，然后进入运行状态。

就绪探测与租约
--------------

- 探测按顺序进行：输出日志标记、socket 存在、QMP 协商；vHost 还可以等待
  指定的客户机串口输出。
- 每个探测必须在进程启动后的 ``--ready-timeout``\ （默认 120 秒）内成功；
  vHost 的串口标记可以用 ``serial.timeout`` 单独设置时限。
- 设备通过探测后向每个依赖者交出租约；最后一个租约释放后设备才停止，因此
  vHost 总是先于设备停止。
- 不同机器之间互不等待；某台机器的 vHost 以状态 0 退出只结束该机器。

关闭与会话结束
--------------

- 第一次 SIGINT 或 SIGTERM 触发有序关闭，后续信号跳过剩余等待时间；
- 每个进程组先收到 SIGTERM，5 秒后仍在运行的进程收到 SIGKILL；
- ``--run-for`` 在全部进程就绪后限定运行时长；开发容器会设置标准输入生命线，
  客户端退出时会话结束；
- vHost 以状态 0 退出会结束本机；其他退出、探测失败或磁盘准备失败会取消整个
  会话；
- 结束后删除 socket、overlay 与内存池，日志和元数据保留。

产物与 verdict
--------------

.. list-table::
   :header-rows: 1

   * - 路径
     - 内容
   * - ``plan.json``、``options.json``
     - 执行计划与运行选项
   * - ``manifest.json``
     - 会话创建的资源清单，供 ``clean`` 使用
   * - ``<machine>/layout.json``
     - 该机器内存池的区域、偏移与大小
   * - ``<machine>/vhost/output.log``、``<machine>/<device>/output.log``
     - vHost 与设备进程的命令输出
   * - ``<machine>/vhost/serial.log``
     - vHost 操作系统串口日志
   * - ``verdict.json``
     - 状态、未停止的进程与清理错误

launcher 最后打印 ``[COSIM_VERDICT]`` 行，内容与 ``verdict.json`` 一致。
launcher 被杀死或异常退出后，用 ``cosim clean <run-dir>`` 按清单删除资源；
只有 launcher 及其全部进程都已退出并释放 ``session.lock`` 时才会执行。

相关页面
--------

- :doc:`components`
- :doc:`memory_model`
- :ref:`会话生命周期与资源管理 <launcher-session-lifecycle>`
- :ref:`会话排错 <launcher-debugging-sessions>`
- :ref:`如何编写拓扑 YAML <topo-write-topology>`

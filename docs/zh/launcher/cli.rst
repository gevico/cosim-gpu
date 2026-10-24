.. SPDX-License-Identifier: Apache-2.0

.. _launcher-cli:

命令与选项
===========

本页是 ``cosim``\ 命令的速查页，说明子命令、常用选项、输出和退出码。

全局选项
---------

``--resources``\ 是唯一的全局选项，默认 ``resources/``\ ，用于解析没有相对导入文件定位的导入路径。资源路径相对工作区根目录解析，不含 ``/``\ 的可执行文件名在生成计划时从 ``PATH``\ 查找。

子命令
-------

.. list-table::
   :header-rows: 1

   * - 命令
     - 主要参数
     - 输出与作用
   * - ``validate``
     - 拓扑、``--assets``
     - 校验文档、标识符和内存布局；``--assets``\ 额外检查本地输入文件。成功时打印机器数和设备数。
   * - ``graph``
     - 拓扑
     - 以 Mermaid flowchart 打印机器与设备的连接。
   * - ``schema``
     - 无
     - 打印拓扑文档的 JSON Schema。
   * - ``run``
     - 拓扑、目录选项和运行选项
     - 启动并监督会话，输出事件行和最终 verdict。
   * - ``clean``
     - 运行目录
     - 删除 ``manifest.json``\ 记录的会话资源，保留日志。

run 选项
---------

.. list-table::
   :header-rows: 1

   * - 选项
     - 默认值
     - 说明
   * - ``--dry-run``
     - 关闭
     - 解析镜像配方并打印启动计划，不构建镜像也不启动进程。
   * - ``--run-dir``
     - ``.cosim/<12 位随机名>``
     - 新会话目录；dry-run 默认使用 ``.cosim/dry-run``\ 。
   * - ``--pool-dir``
     - Linux 上为 ``/dev/shm/cosim-<name>-<hash>``\ ，其他系统为 ``<run-dir>/memory``
     - 共享内存池目录。
   * - ``--ready-timeout``
     - ``120``
     - 每个进程从启动到全部就绪探测成功的秒数上限。
   * - ``--run-for``
     - 无
     - 全部进程就绪后继续运行的秒数，到期即结束会话。
   * - ``--qemu-img``
     - ``qemu-img``
     - 创建缺失镜像和 overlay 的工具。
   * - ``--stdin-lifeline``
     - 环境变量 ``COSIM_STDIN_LIFELINE``
     - 标准输入关闭时结束会话；开发容器会设置该变量。

典型工作流
-----------

.. code-block:: bash

   # 构建启动器（首次需要）
   just build-cosim
   # 只校验文档、标识符和本地输入文件
   just run-cli validate resources/machines/gpu-8.yaml  --assets
   # 查看解析后的执行计划
   just run-topology resources/machines/mixed-models.yaml --dry-run
   # 查看机器与设备的连接
   just run-cli graph resources/clusters/cluster-4x8.yaml
   # 打印拓扑文档的 JSON Schema
   just run-cli schema
   # 运行并监督一个会话
   just run-topology resources/machines/single-gpu.yaml
   # 回收异常退出留下的会话资源
   just run-cli clean .cosim/<name>

``just run-cli``\ 把参数直接透传给 ``cosim``\ ；``just run-topology``\ 在开发容器中运行，并把仓库根目录作为工作区。

事件、退出码与 verdict
-----------------------

- 运行期间按行输出 ``started``\ 、``ready``\ 、``exited``\ 和 ``stopped``\ 事件。
- 第一个 SIGINT 或 SIGTERM 触发有序关闭；后续信号跳过剩余等待时间。
- 退出码：verdict 为 ``PASS``\ 时返回 0，否则返回 1；命令行或加载错误同样返回 1。
- 最后一行是 ``[COSIM_VERDICT]``\ 加 JSON，同时写入运行目录的 ``verdict.json``\ 。

.. code-block:: text

   [COSIM_VERDICT] {"status":"PASS","reason":null,"cleanup_errors":[],"users_stopped":true}

源码与依据
-----------

- 命令与选项定义：``crates/cosim-cli/src/main.rs``\ 。
- ``Verdict``\ 与 ``Status``\ ：``crates/cosim-runtime/src/session.rs``\ 。
- 计划的结构：``crates/cosim-runtime/src/plan.rs``\ 。
- 示例拓扑与 vHost：``resources/machines/``\ 、``resources/vhosts/qemu.yaml``\ 。

相关页面
---------

- :doc:`yaml_pipeline`\ ：输入文档如何变成计划。
- :doc:`session_lifecycle`\ ：``run``\ 启动之后发生什么。
- :doc:`debugging_sessions`\ ：如何阅读日志和 verdict。
- :ref:`ref-files-and-artifacts`\ ：会话目录与构建产物的路径。

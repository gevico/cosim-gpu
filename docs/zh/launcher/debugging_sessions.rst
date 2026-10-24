.. SPDX-License-Identifier: Apache-2.0

.. _launcher-debugging-sessions:

会话排错
=========

本页说明如何阅读会话事件、日志和 verdict，如何从常见启动失败中定位第一个出错的组件，以及如何安全地回收异常退出留下的资源。

会话事件与日志
---------------

- ``run``\ 启动时打印 ``session: <run-dir>``\ ，随后按行输出 ``started``\ 、``ready``\ 、``exited``\ 和 ``stopped``\ 事件。
- 每个进程的标准输出与标准错误写入自己的工作目录下的 ``output.log``\ ，gem5 的 ``m5out/``\ 也位于该目录。
- vHost 的串口输出写入 ``<machine>/vhost/serial.log``\ ，同时由串口 socket 提供交互。
- ``verdict.json``\ 记录最终结果；同样的内容以 ``[COSIM_VERDICT]``\ 行打印在终端。

.. code-block:: bash

   # 会话目录由 run 的 session 行给出，默认在 .cosim/ 下
   ls .cosim/<name>
   # 汇总各进程日志的尾部
   tail -n 50 .cosim/<name>/m0/mi300x-0/output.log
   tail -n 50 .cosim/<name>/m0/vhost/output.log
   tail -n 50 .cosim/<name>/m0/vhost/serial.log
   cat .cosim/<name>/verdict.json

阅读 verdict
-------------

.. list-table::
   :header-rows: 1

   * - 字段
     - 含义
   * - ``status``
     - ``PASS``\ 或 ``FAIL``\ 。
   * - ``reason``
     - 第一个失败原因；没有失败时为 ``null``\ 。
   * - ``cleanup_errors``
     - 释放会话资源时的错误列表。
   * - ``users_stopped``
     - 是否确认所有自有进程都已退出；为 ``false``\ 时资源会被保留以便排查。

.. code-block:: json

   {
     "status": "FAIL",
     "reason": "host m0 exited with status 1",
     "cleanup_errors": [],
     "users_stopped": true
   }

常见启动失败
-------------

.. list-table::
   :header-rows: 1

   * - 症状
     - 首先检查
     - 处理
   * - 加载报未知字段或未知模板
     - YAML 字段名、模板名与 ``use``\ 引用
     - 按 ``cosim schema``\ 修正文档。
   * - 导入文件不存在
     - 导入路径相对导入文件还是 ``--resources``\ 目录
     - 修正相对路径或传入正确的 ``--resources``\ 。
   * - 程序找不到
     - ``runtime.binary``\ 与 ``PATH``
     - 写工作区相对路径，或先构建对应二进制。
   * - 设备就绪超时
     - 设备 ``output.log``\ 中的就绪标记与 socket
     - 确认二进制可运行、``ready_log``\ 正确、socket 未被占用。
   * - host 就绪超时
     - ``serial.wait_for``\ 标记与 ``serial.timeout``
     - 核对客户机命令行与串口配置。
   * - 内存池容量不足
     - 内存池目录所在文件系统剩余空间与并发会话
     - 释放空间或清理其他会话后重试。
   * - 远端放置被拒绝
     - ``placement.agent``
     - ``cosim run``\ 仅在本地执行，移除远端放置。
   * - ``clean``\ 拒绝执行
     - launcher 或子进程是否仍存活、``session.lock``\ 是否被持有
     - 先结束相关进程，再执行 ``clean``\ 。

清理与残留资源
---------------

- 正常结束时 launcher 已经删除 socket、overlay、内存池和内存池目录，只保留日志与元数据。
- launcher 被杀死或异常退出后，用 ``cosim clean <run-dir>``\ 删除 ``manifest.json``\ 中列出的资源。
- ``clean``\ 只从所有权标记属于本会话的内存池目录中删除内容，不会误删其他会话。
- 若 ``clean``\ 无法执行，先检查 ``session.lock``\ 是否仍被进程持有，再检查 ``manifest.json``\ 中的资源路径。

源码与依据
-----------

- 事件与 verdict：``crates/cosim-runtime/src/session.rs``\ 。
- 就绪探测：``crates/cosim-runtime/src/probe.rs``\ 。
- 清理：``crates/cosim-runtime/src/manifest.rs``\ 。
- 会话文件命名：``crates/cosim-runtime/src/layout.rs``\ 。

相关页面
---------

- :doc:`session_lifecycle`\ ：会话生命周期与资源规则。
- :doc:`cli`\ ：命令、选项与退出码。
- :ref:`ref-known-issues`\ ：已知问题的 symptom/cause/fix 全量清单。
- :ref:`sim-debugging-models`\ ：gem5 模型侧的调试方法。

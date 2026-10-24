.. SPDX-License-Identifier: Apache-2.0

.. _gs-first-session:

首次会话
========

本页用 vHost 选择 ``ubuntu/24.04/x86_64/rocm/7.0`` 的 ``single-gpu`` 机器启动第一次联合仿真
会话，连接客户机串口并正常关闭。

前置条件
--------

- 已执行 :doc:`install` 的构建步骤，``build/rocm-local-installed/disk`` 与
  ``build/rocm-local-installed/kernel`` 存在；
- Linux 主机上 ``/dev/kvm`` 可访问；
- 已准备客户机镜像，见 :doc:`guest_image`；
- 主机有足够空间保存会话内存池（标准 ``single-gpu`` 约 24 GiB）。

启动命令
--------

.. code-block:: bash

   just run-topology resources/machines/single-gpu.yaml \


recipe 调用 Rust ``cosim`` launcher，加载拓扑与 vHost，检查本机输入文件，
然后按 :doc:`../architecture/execution_flow` 描述的顺序启动进程。launcher 会
先打印会话目录，例如 ``session: .cosim/1f0c3a4b5c6d``。

会话做了什么
------------

1. 解析并校验 YAML：导入 host 与设备模板，展开机器列表；
2. 结合本机页大小、``PATH`` 与磁盘锁目录生成执行计划；
3. 创建会话目录，写入 manifest、plan 与 options；
4. 创建共享内存池并预留容量，准备根磁盘的 qcow2 overlay；
5. 启动 gem5 MI300X 设备进程，等待其 vfio-user socket 与监听标记；
6. 启动 host QEMU，完成 QMP 握手，客户机从直接内核启动；
7. 客户机启动后，``cosim-gpu-initialize.service`` 约 40 秒完成 GPU 初始化。

.. note::

   设备进程先于 host 启动，host 先于设备停止；会话在 host 以状态 0 退出时
   结束。默认每个进程有 120 秒就绪时间，可用 ``--ready-timeout`` 调整。

连接客户机串口
--------------

host 把串口暴露为 Unix socket，同时写日志文件。用任意 Unix socket 客户端
连接，例如：

.. code-block:: bash

   socat -,raw,echo=0 unix-connect:.cosim/<session>/m0/serial.sock

没有 ``socat`` 时可以使用 ``nc -U .cosim/<session>/m0/serial.sock``。只想
查看输出时跟踪日志：

.. code-block:: bash

   tail -f .cosim/<session>/m0/vhost/serial.log

客户机 root 串口自动登录，可以直接执行命令。首次登录后建议先确认 GPU 状态，
见 :doc:`verify_guest`。

会话产物
--------

运行目录默认是 ``.cosim/<随机名>``，可以用 ``--run-dir`` 指定固定路径：

.. list-table::
   :header-rows: 1

   * - 路径
     - 内容
   * - ``plan.json``、``options.json``
     - 解析后的执行计划与本次运行选项
   * - ``manifest.json``、``verdict.json``
     - 会话资源清单与最终 verdict
   * - ``m0/layout.json``
     - 每台机器的内存池区域布局
   * - ``m0/serial.sock``、``m0/vhost/serial.log``
     - 客户机串口与串口日志
   * - ``m0/vhost/output.log``、``m0/mi300x-0/output.log``
     - host 与各设备进程的输出日志

关闭会话
--------

- 在客户机内执行 ``poweroff``，host 正常退出后会话结束；
- 或在启动 launcher 的终端按一次 Ctrl-C，触发有序关闭：先停 host，再停设备，
  然后删除 socket、overlay 与内存池；
- 结束后 launcher 打印最后一行 ``[COSIM_VERDICT]``，包含状态与清理结果；
- launcher 被强行杀死后，用 ``just run-cli clean .cosim/<session>`` 清理残留
  资源，日志会保留。

.. tip::

   只在需要限时运行时使用 ``--run-for 60``；它会在全部进程就绪后计时结束
   会话。开发容器会设置标准输入生命线，客户端退出时会话自动结束。

相关页面
--------

- :doc:`verify_guest`
- :doc:`guest_image`
- :ref:`会话执行流程 <arch-execution-flow>`
- :ref:`会话生命周期与资源管理 <launcher-session-lifecycle>`
- :ref:`会话排错 <launcher-debugging-sessions>`

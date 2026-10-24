.. SPDX-License-Identifier: Apache-2.0


.. _topo-machines-host-only:

host-only 机器
==============

概述
----

``host-only`` 是无设备的 TCG 板卡：一台 ``vhost-x86-tcg`` 主机以暂停状态启动，不带设备，也不启动客户机。它用来验证 QEMU 进程、内存池、QMP 与串口管理这条会话链路本身。

拓扑
----

.. code-block:: yaml

   # resources/machines/host-only.yaml
   version: 1
   imports: [vhosts/qemu.yaml, vhosts/vhost-x86-tcg.yaml]
   templates:
     vhost-x86-node:
       vhost: {use: vhost-x86-tcg}
   machines:
     - {id: m0, use: vhost-x86-node}

- 机器数量：1（``m0``\ ）；只有主机，没有 ``devices`` 列表。
- ``vhost-x86-tcg`` 继承 ``vhost-x86`` 的 Q35 machine 与内存映射，只改内存、CPU、加速器与可执行文件。
- vHost 以 ``-S -nodefaults`` 暂停启动，且没有镜像或内核，因此不会运行客户机系统。

硬件资源
--------

.. list-table::
   :header-rows: 1

   * - 资源
     - 值
     - 来源
   * - 机器
     - 1 台（``m0``\ ）
     - ``resources/machines/host-only.yaml``
   * - vHost 配置
     - ``vhost-x86-tcg``\ ：``q35``\ 、``tcg``\ 、``qemu64`` CPU
     - ``resources/vhosts/vhost-x86-tcg.yaml``
   * - 客户机 RAM
     - 64 MiB
     - ``resources/vhosts/vhost-x86-tcg.yaml``
   * - vCPU
     - 1
     - 同上
   * - 设备
     - 无
     - —
   * - 内存池
     - 64 MiB
     - 主机 RAM
   * - 可执行文件
     - ``qemu-system-x86_64``\ （从 ``PATH`` 查找）
     - ``resources/vhosts/vhost-x86-tcg.yaml``
   * - vHost
     - 无
     - —

软件栈
------

- 没有客户机 OS：主机暂停在 QEMU 启动阶段，不执行内核。
- 就绪探测只覆盖 QEMU 侧：串口 socket 存在、QMP 协商成功；没有 ``serial.wait_for`` 标记。
- 这台板卡用于测试会话监督：运行目录与内存池的创建、QMP 管理、进程组停止与资源清理。

运行该机器
----------

.. code-block:: bash

   # 只校验与预览
   just run-cli validate resources/machines/host-only.yaml
   just run-topology resources/machines/host-only.yaml --dry-run
   # 运行 1 秒后结束会话（主机处于暂停状态）
   just run-topology-dev resources/machines/host-only.yaml --run-for 1

- ``--run-for`` 在全部进程就绪后开始计时，适合这种无客户机的冒烟运行。
- 会话结束后保留 ``plan.json``\ 、``layout.json``\ 、``output.log`` 与 ``verdict.json``\ ，内存池与 socket 被删除。
- 生命周期见 :ref:`launcher-session-lifecycle`\ 。

验证
----

- 计划输出为 1 个主机进程、0 个设备进程，内存池 64 MiB。
- 会话测试套件使用 TCG 主机跑通这条路径，另有两台机器的 ``tcg-pair.yaml`` 变体，见 :doc:`../multi_machine`\ 。
- 结束后的 verdict 记录进程停止状态；无法确认退出时会保留资源并记录 ``users_stopped: false``\ 。

限制
----

- 主机处于暂停状态，不执行客户机；需要客户机行为时使用 ``single-gpu`` 等板卡。
- 只有 TCG 加速，不覆盖 KVM 下的客户机路径。
- 没有设备，因此不覆盖 vfio-user 设备链路；对应样例见 :doc:`qemu_device`\ 。
- 运行会话需要 Linux glibc 与 ``setpriv``\ 。

相关页面
--------

- vHost 配置：:doc:`../hosts/index`
- 机器目录：:doc:`index`
- qemu-device 板卡：:doc:`qemu_device`
- 多机版本：:doc:`../multi_machine`
- 会话生命周期：:ref:`launcher-session-lifecycle`
- 源码：``resources/machines/host-only.yaml``\ 、``resources/vhosts/vhost-x86-tcg.yaml``

.. SPDX-License-Identifier: Apache-2.0

.. _gs-platform-container:

开发容器
========

本页说明开发容器提供的构建环境、``scripts/host/dev.sh`` 的行为，以及在容器中
构建、规划与运行时会话的限制。Linux 原生运行见 :doc:`linux`。

适用场景
--------

- macOS 与 Windows 默认使用开发容器完成构建、``plan``/``graph`` 与 TCG
  会话；可引导的 KVM 客户机仍需要 Linux 主机。
- Linux 主机缺少 gem5、QEMU 或 Rust 构建依赖时，可以只把构建放进容器，
  运行仍在主机上进行。
- 需要与 CI 一致的构建环境时使用容器。

构建与选择环境
--------------

.. code-block:: bash

   just dev-image                  # 构建 cosim-dev:local 镜像
   export COSIM_ENV=container      # 显式选择容器路径

``just dev-image`` 根据 ``scripts/host/Dockerfile.dev`` 构建 ``cosim-dev:local``：
基于 Ubuntu 24.04，包含 gem5 与 QEMU 构建依赖、Rust 工具链、QEMU 和
``qemu-img``。``COSIM_ENV`` 未设置时，Linux 用 ``host``，其他系统用
``container``。

dev.sh 的行为
-------------

构建、拓扑与 Rust 检查 recipe 通过 ``scripts/host/dev.sh`` 执行，行为如下：

.. list-table::
   :header-rows: 1

   * - 方面
     - 行为
   * - 挂载
     - 源码树按主机上的绝对路径挂载，YAML、计划与日志中的路径在容器内外一致
   * - 用户
     - 以当前用户的 uid/gid 运行，产物归属与主机一致
   * - 生命周期
     - ``docker run --rm --init``；命令结束后删除容器
   * - KVM
     - 主机存在 ``/dev/kvm`` 时透传给容器
   * - 共享内存
     - 容器有自己的 ``/dev/shm``，大小上限等于 Docker daemon 的内存
   * - 缓存
     - Cargo 缓存与产物写入仓库顶层的 ``build/``
   * - 磁盘锁
     - ``COSIM_DISK_LOCK_DIR`` 对应目录挂载进容器，供镜像租约使用
   * - 标准输入生命线
     - 设置 ``COSIM_STDIN_LIFELINE=1``，客户端退出时会话结束

源码树之外的文件在容器中不可见，需要时用 ``--mount`` 显式挂载。

在容器中工作
------------

.. code-block:: bash

   just dev-shell                                  # 打开一次性的交互 shell
   COSIM_ENV=container just build-cosim            # 在容器中构建 launcher
   just run-topology resources/machines/single-gpu.yaml --dry-run
   just run-topology resources/machines/host-only.yaml --run-for 1

``just run-topology`` 与 ``just run-cli`` 本身也走 ``dev.sh``；设置
``COSIM_ENV=container`` 后 ``cosim run`` 在容器内执行。host-only 与 TCG
会话不需要 KVM，可以在容器中运行。

限制
----

- 没有 ``/dev/kvm`` 时无法启动可引导客户机，只能构建、规划与运行 TCG 会话；
- 容器退出后其 ``/dev/shm`` 中的内存池随之消失，会话不能跨容器保留；
- 会话目录在挂载的源码树内，日志与 verdict 会保留在主机上；
- 嵌套文件系统与 Docker 网络会带来额外开销，长时间仿真建议在 Linux 主机
  原生运行。

.. note::

   开发容器只用于开发与检查。客户机镜像构建需要真实的 ``/dev/kvm`` 与
   QEMU，通常直接在 Linux 主机上执行。

相关页面
--------

- :doc:`../requirements`
- :doc:`../install`
- :doc:`linux`
- :ref:`Cosim Launcher 介绍 <launcher-index>`

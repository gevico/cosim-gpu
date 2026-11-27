.. SPDX-License-Identifier: Apache-2.0

.. _gs-requirements:

环境与前置条件
==============

本页列出运行联合仿真所需的主机、工具、磁盘与内存条件，并给出一次性的自查
命令。组件版本以 :ref:`版本矩阵 <ref-version-matrix>` 为准，本页不重复维护。

主机环境
--------

- 标准路径：Linux x86_64 主机，``/dev/kvm`` 可访问。随附的客户机镜像面向
  x86_64，启动可引导的客户机需要 KVM。
- 没有 KVM 时仍可以构建组件、执行 ``cosim validate``、
  ``cosim run <topology.yaml> --dry-run`` 和 ``cosim graph``，以及运行暂停状态
  的 TCG host-only 会话；这类会话不启动可引导客户机。
- Linux aarch64 主机可用于构建与规划；随附的客户机镜像不是 AArch64 版本。
- macOS 与 Windows 通过开发容器完成构建、规划和 TCG 会话；可引导客户机需要
  Linux 主机与 KVM，见 :doc:`platforms/container`。
- 构建 recipe 未提供 RISC-V 主机 profile。

工具与版本
----------

.. list-table::
   :header-rows: 1

   * - 要求
     - 说明
   * - 主机系统
     - 带 KVM 的 Linux x86_64；macOS 与 Windows 走开发容器
   * - Rust 与 Cargo
     - 1.95 及以上，用于构建 ``cosim`` launcher
   * - just
     - 1.46 及以上；所有任务都是 ``justfile`` 中的 recipe
   * - Docker
     - 守护进程运行，当前用户属于 ``docker`` 组；开发容器与 GPU 应用构建使用
   * - KVM
     - ``/dev/kvm`` 存在且当前用户可读写
   * - QEMU
     - 由 ``qemu`` 子模块构建；样例指向 ``build/qemu/qemu-system-x86_64``
   * - 磁盘工具
     - 同次 QEMU 构建生成的 ``build/qemu/qemu-img``，用于镜像校验、创建与会话 overlay
   * - 其他工具
     - ``git``、``screen``、``unzip``；镜像构建另需 Packer 与 Ansible

磁盘与内存
----------

.. list-table::
   :header-rows: 1

   * - 资源
     - 最低
     - 推荐
   * - 磁盘
     - 120 GB 可用（约 55 GB 镜像加构建产物）
     - 150 GB 以上
   * - 内存
     - 16 GB
     - 32 GB 以上，尤其是 gem5 链接和 8 GPU 机器
   * - 共享内存文件系统
     - 能容纳所选机器的完整内存池
     - ``single-gpu`` 标准会话约 24 GiB

检查清单
--------

.. code-block:: bash

   just --list                 # 任务入口
   ls -l /dev/kvm              # KVM 是否存在且可访问
   docker info >/dev/null      # 开发容器与 gem5 容器
   df -h .                     # 磁盘空间
   free -h                     # 内存

某项检查失败时，先看 :doc:`platforms/linux` 的依赖与权限说明，或改用
:doc:`platforms/container` 继续构建与规划。

相关页面
--------

- :doc:`install`
- :doc:`platforms/linux`
- :doc:`platforms/container`
- :ref:`版本矩阵 <ref-version-matrix>`

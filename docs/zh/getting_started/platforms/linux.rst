.. SPDX-License-Identifier: Apache-2.0

.. _gs-platform-linux:

Linux 主机
==========

本页说明在 Linux 主机上原生构建和运行联合仿真的依赖、KVM 权限和发行版差异。
使用容器时看 :doc:`container`。

适用场景
--------

主机满足以下条件时直接原生运行，性能最好，也便于连接真实硬件与调试：

- Linux x86_64，且 ``/dev/kvm`` 对当前用户可读写；
- 已安装 ``scripts/host/Dockerfile.dev`` 列出的 gem5、QEMU 与 Rust 构建依赖；
- Docker 守护进程可用（开发容器与 GPU 应用构建使用）；
- 磁盘与内存满足 :doc:`../requirements` 的下限。

缺少构建依赖或使用其他发行版时，可以只把构建放进开发容器，见
:doc:`container`。

系统依赖
--------

完整软件包列表以 ``scripts/host/Dockerfile.dev`` 为准，主要分为以下几类：

.. list-table::
   :header-rows: 1

   * - 类别
     - 典型软件包
     - 用途
   * - 编译工具链
     - ``build-essential``、``cmake``、``m4``、``ninja-build``
     - 编译 QEMU 与 gem5
   * - gem5 依赖
     - ``scons``、``python3-dev``、``libboost-all-dev``、``libprotobuf-dev``
     - gem5 构建与 Python 脚本
   * - QEMU 依赖
     - ``libglib2.0-dev``、``libpixman-1-dev``、``libslirp-dev``、``libjson-c-dev``
     - QEMU softmmu 与 vfio-user 后端
   * - 测试依赖
     - ``libcmocka-dev``、``python3-venv``
     - QEMU 单元测试与 Python 虚拟环境
   * - 镜像构建
     - ``ansible-core``、``python3-tomli``、``unzip``
     - Packer/Ansible 客户机镜像构建
   * - Rust
     - Rust 1.95 及以上与 Cargo
     - 构建 ``cosim`` launcher

gem5 二进制链接 Ubuntu 24.04 的库，建议在与该发行版兼容的环境中构建；
发行版差异较大时使用开发容器。

KVM 与权限
----------

.. code-block:: bash

   ls -l /dev/kvm
   test -r /dev/kvm && test -w /dev/kvm && echo kvm-ok

``/dev/kvm`` 通常属于 ``root:kvm``、权限 ``0660``。把当前用户加入 ``kvm``
组后重新登录：

.. code-block:: bash

   sudo usermod -aG kvm "$USER"

Docker 也需要当前用户可访问：确认用户在 ``docker`` 组且守护进程正在运行。

WSL2 与嵌套虚拟化
-----------------

- WSL2 内需要开启嵌套虚拟化，并让 ``/dev/kvm`` 在发行版内可见；
- 源码与构建产物放在 ext4 文件系统上，不要放在 ``/mnt/c`` 等挂载盘；
- 内存与 CPU 按 :doc:`../requirements` 的下限分配，gem5 链接阶段尤其需要内存；
- 容器路径同样需要把 ``/dev/kvm`` 透传给容器。

验证环境
--------

.. code-block:: bash

   git submodule status
   just --list
   docker info >/dev/null && echo docker-ok
   ls -l /dev/kvm
   build/qemu/qemu-img --version

以上检查通过后，按 :doc:`../install` 构建并进入 :doc:`../first_session`。

相关页面
--------

- :doc:`../requirements`
- :doc:`../install`
- :doc:`container`
- :ref:`版本矩阵 <ref-version-matrix>`

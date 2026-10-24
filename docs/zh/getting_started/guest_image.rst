.. SPDX-License-Identifier: Apache-2.0

.. _gs-guest-image:

客户机镜像
==========

本页说明客户机镜像包含什么、如何复用已构建的内核与磁盘，以及在需要时如何
重建和校验。第一次使用通常只需要 ``just build-disk``。

镜像内容
--------

.. list-table::
   :header-rows: 1

   * - 内容
     - 说明
   * - 操作系统
     - Ubuntu 24.04.2 LTS，x86_64
   * - 内核
     - Linux 6.8.0-124-generic，与导出的磁盘成对使用
   * - GPU 软件栈
     - ROCm 7.0、amdgpu DKMS 模块；PyTorch 来自 rocm6.0 wheel 源
   * - GPU 数据
     - MI300X VBIOS ROM 与 IP discovery 固件
   * - 初始化
     - ``cosim-gpu-initialize.service`` 在启动时写入 ROM 并加载 amdgpu
   * - 登录
     - root 串口自动登录，供脚本与交互使用
   * - 配套 vHost
     - ``resources/vhosts/qemu.yaml``，声明内核、根磁盘与 cmdline

镜像配方与 Ansible playbook 由本仓库维护在
``resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/``；
``recipe.toml`` 记录 Ubuntu 版本、内核版本、Packer 模板与导出产物。

复用预构建镜像
--------------

.. code-block:: bash

   just build-disk        # 构建内核与磁盘，并安装本地副本

``just build-disk`` 在 ``build/rocm-local`` 生成 raw 格式产物，并把标准示例
使用的副本安装到以下位置：

.. list-table::
   :header-rows: 1

   * - 产物
     - 路径
     - 约大小
   * - 磁盘镜像
     - ``build/rocm-local-installed/disk``
     - 55 GB
   * - 内核
     - ``build/rocm-local-installed/kernel``
     - 64 MB

``resources/vhosts/qemu.yaml`` 直接引用这两个路径，并用
``modprobe.blacklist=amdgpu`` 让初始化服务按正确顺序加载驱动。

重新构建镜像
------------

镜像由 Packer 启动真实 QEMU/KVM 虚拟机，再由 Ansible 安装软件包并配置
ROCm，最后导出磁盘与配套内核。重建需要：

- Linux x86_64 主机与可访问的 ``/dev/kvm``；
- 构建与压缩至少 60 GiB 可用磁盘，以及容纳 8 GiB 构建虚拟机的内存；
- QEMU、``qemu-img``、Ansible、``python3-tomli``、curl、unzip、Perl 的
  ``shasum`` 与 binutils；
- 访问 Canonical、AMD、HashiCorp 与 PyTorch 软件源。

.. code-block:: bash

   just build-rocm-assets build/rocm-custom    # 生成可复用 bundle
   just build-disk                             # 生成并安装本地标准副本
   just test-rocm-assets build/rocm-custom     # 校验复用与损坏拒绝

``just build-rocm-assets`` 构建一次可复用的内核/磁盘 bundle；
``just build-disk`` 面向标准示例安装独立副本。配方固定 Packer 与插件版本，
并校验 ISO 与 Packer 下载的摘要。

.. tip::

   软件包下载较慢时，可以先把构建虚拟机内的 apt 源换成可用镜像再重新执行；
   输入相同的已完成产物会经过校验后被复用，不需要从头重跑。

产物清单
--------

bundle 目录包含以下文件，供会话与校验使用：

.. list-table::
   :header-rows: 1

   * - 文件
     - 用途
   * - ``kernel``、``disk``
     - 直接内核启动与根磁盘，必须成对使用
   * - ``manifest.json``
     - 源码与输入标识、构建时间、安装版本和 SHA-256
   * - ``kernel-release``、``os-release``
     - 实际内核版本与系统版本
   * - ``image-packages.tsv``、``python-packages.json``
     - 已安装软件包清单
   * - ``amdgpu-module.txt``、``hipcc-version.txt``
     - 驱动模块与 HIP 编译器版本
   * - 构建日志
     - Packer 与 Ansible 完整日志

校验与复用
----------

- 清单记录输入标识与实际安装版本；输入相同的已完成产物在验证后可以复用。
- 镜像完整性使用 ``qemu-img check``，raw 产物校验配对文件摘要与镜像信息。
- 回归程序为每个用例创建独立的磁盘 overlay，避免互相污染。
- 校验配方：``just check-rocm-image`` 使用真实 Packer 插件校验完整配置，
  ``just check-rocm-syntax`` 只校验模板与 playbook，不构建镜像。
- CI 中的镜像构建、缓存与复用流程见 :ref:`CI 与回归 <contrib-ci>`。

.. warning::

   随附镜像只面向 x86_64；AArch64 机器没有可引导的客户机镜像。每台机器都在
   ``vhost`` 中独立选择镜像。

相关页面
--------

- :doc:`install`
- :doc:`first_session`
- :doc:`verify_guest`
- :ref:`ref-vhost-image-recipe`
- :ref:`CI 与回归 <contrib-ci>`

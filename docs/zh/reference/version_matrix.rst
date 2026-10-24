.. SPDX-License-Identifier: Apache-2.0

.. _ref-version-matrix:

版本矩阵
========

本页是版本与镜像信息的唯一事实源。每条记录都区分记录值、最低版本和校验方式：记录值用于复现，最低版本用于判断兼容性，校验方式给出在工作树中核对的方法。

组件版本
--------

.. list-table::
   :header-rows: 1

   * - 组件
     - 版本或取值
     - 类型
     - 证据
   * - QEMU（子模块记录值）
     - v11.1.2，提交 ``4fc49f46``
     - 记录值
     - ``third_party/qemu/VERSION``；``git ls-tree HEAD qemu``
   * - QEMU（系统回退，legacy launcher）
     - 10.1 及以上，提供 ``vfio-user-pci``
     - 最低版本
     - ``scripts/host/cosim_launch.sh`` 的启动前检查
   * - gem5（子模块）
     - ``gevico/gem5`` 的 ``gevico/cosim-gpu`` 分支；当前检出 ``v25.0.0.0-961-gcc9d5dd248``
     - 记录值
     - ``git submodule status gem5``；``git -C gem5 describe --tags --always``
   * - gem5 构建目标
     - ``VEGA_X86``
     - 固定值
     - ``justfile`` 的 ``gem5_build_dir``
   * - GPU 模型
     - MI300X，gfx942，PCI ``0x1002`` 与 ``0x74a0``
     - 固定值
     - ``resources/devices/gpu/mi300x.yaml``
   * - 一致性协议
     - ``GPU_VIPER``
     - 固定值
     - ``third_party/gem5/configs/example/gpufs/Disjoint_VIPER.py``
   * - Rust
     - 1.95 及以上
     - 最低版本
     - ``Cargo.toml`` 的 ``rust-version``
   * - 客户机操作系统
     - Ubuntu 24.04.2 LTS
     - 记录值
     - 镜像 ``recipe.toml``
   * - 客户机内核
     - ``6.8.0-124-generic``
     - 记录值
     - 镜像 ``recipe.toml``
   * - ROCm
     - 7.0（apt 仓库 ``amdgpu/7.0`` 与 ``rocm/apt/7.0``）
     - 记录值
     - ``provision.yml``
   * - amdgpu DKMS
     - 随 ROCm 7.0
     - 记录值
     - ``provision.yml``
   * - PyTorch wheel 通道
     - ``rocm6.0``
     - 记录值
     - ``provision.yml`` （镜像内固定通道）
   * - 客户机 ROM 与 discovery 固件
     - ``mi200.rom``、``mi300.rom``、``mi300_discovery``、``mi350_discovery``
     - 记录值
     - ``provision.yml``；文件位于镜像 recipe ``files/``
   * - Packer
     - 1.16.1
     - 记录值
     - 镜像 ``build.sh``
   * - Packer 插件
     - qemu 1.1.7、ansible 1.1.6
     - 记录值
     - 镜像 ``image.pkr.hcl``

QEMU 的子模块记录值是 v11.1.2 的发布提交。工作树中的 ``qemu`` 检出可能位于其他分支，因此构建前应以 ``git -C qemu describe --tags --always`` 为准；发布说明中的 QEMU 版本指项目 gitlink 记录值。

镜像与容器
----------

.. list-table::
   :header-rows: 1

   * - 名称
     - 角色
     - 来源
   * - ``cosim-dev:local``
     - 开发容器镜像；同时是 legacy shell launcher 的 gem5 容器默认镜像
     - ``just dev-image``，基于 ``scripts/host/Dockerfile.dev`` （Ubuntu 24.04、third_party/gem5/QEMU 构建依赖、Rust、QEMU、``qemu-img``）
   * - ``ghcr.io/third_party/gem5/gpu-fs:latest``
     - 客户机 GPU 测试程序的编译镜像；``just build-gpu-tests`` 与 ``just build-gpu-app`` 的 ``GPU_APP_BUILD_IMAGE`` 默认值
     - 外部镜像；可用 ``GPU_APP_BUILD_IMAGE`` 覆盖
   * - 客户机内核与磁盘
     - ``build/rocm-local-installed/kernel`` 与 ``build/rocm-local-installed/disk``
     - ``just build-disk``：先构建 raw bundle 到 ``build/rocm-local``，再安装到本目录

``ghcr.io/third_party/gem5/gpu-fs`` 只用于编译客户机 GPU 程序，不是 cosim 会话的运行镜像；legacy shell launcher 启动 gem5 使用的容器镜像是 ``cosim-dev:local``。

客户机镜像配方
--------------

仓库只有一个客户机镜像配方，标识与产物如下：

.. list-table::
   :header-rows: 1

   * - 项目
     - 值
   * - 配方标识
     - ``ubuntu/24.04/x86_64/rocm/7.0``
   * - 角色与架构
     - ``vhost``，``x86_64``
   * - 目录
     - ``resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/``
   * - 构建入口
     - ``build.sh``；模板 ``image.pkr.hcl``；provisioning ``provision.yml``
   * - 产物
     - ``vmlinux-rocm70`` 内核与 ``disk-image`` 目录
   * - 镜像内磁盘
     - 约 55 GB，构建需要约 60 GB 可用空间
   * - 构建与校验 recipe
     - ``just build-disk``、``just build-rocm-assets``、``just check-rocm-image``、``just check-rocm-syntax``、``just test-rocm-assets``

provenance 与校验
-----------------

记录和核对构建来源时使用以下命令：

.. code-block:: bash

   git submodule status gem5 qemu ext/libvfio-user
   cat third_party/qemu/VERSION
   git -C gem5 describe --tags --always
   just ci-gem5-key
   just ci-rocm-assets key

- gem5 缓存键由项目提交、gem5 提交、开发镜像、构建 recipe 和构建参数共同决定，见 ``scripts/ci/runtime_artifact.py``。

- 客户机镜像的 ``manifest.json`` 记录配方标识、内核 release、镜像格式与 kernel/disk 的 SHA-256，见 ``scripts/host/cosim-image``。

- CI 产物以 workflow run 命名并保留固定天数；跨运行复用时校验原始 provenance，见 ``scripts/ci/image_artifact.py`` 与 ``scripts/ci/runtime_artifact.py``。

来源与维护
----------

版本信息来自以下文件；升级版本时同步更新本页：

- ``third_party/qemu/VERSION`` 与仓库 gitlink：QEMU 版本。

- ``git submodule status gem5`` 与 ``justfile``：gem5 检出与构建目标。

- ``Cargo.toml``：Rust 最低版本。

- ``resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/recipe.toml``：客户机 OS 与内核。

- ``resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/provision.yml`` 与 ``build.sh``、``image.pkr.hcl``：ROCm、PyTorch 通道、ROM 与构建工具版本。

相关页面
--------

- 构建产物路径、会话目录与源码地图（产物表的唯一位置）：:doc:`files_and_artifacts`

- 安装与构建流程：:ref:`gs-install`

- 环境与前置条件：:ref:`gs-requirements`

- CI 与构建产物复用：:ref:`contrib-ci`

- 命令与选项：:ref:`launcher-cli`

- 版本不匹配导致的已知问题：:doc:`known_issues`

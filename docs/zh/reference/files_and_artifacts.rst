.. SPDX-License-Identifier: Apache-2.0

.. _ref-files-and-artifacts:

产物、路径与源码地图
====================

本页是仓库目录、构建产物、会话目录、客户机镜像内文件与路径相关环境变量的唯一事实源。路径表按用途分组；版本与 provenance 见 :doc:`version_matrix`。

源码目录
--------

.. list-table::
   :header-rows: 1

   * - 路径
     - 内容
     - 说明
   * - ``crates/cosim-topology/src/``
     - YAML 解码、校验、模板合并、内存布局、适配器与命令渲染
     - Rust 库，暴露 ``load``、``graph``、``schema``
   * - ``crates/cosim-runtime/src/``
     - 执行计划、进程监督、资源所有权、磁盘与清理
     - Rust 库，暴露 ``plan``、``run``、``clean``
   * - ``crates/cosim-cli/src/``
     - 命令行、信号处理、事件与 verdict 输出
     - ``cosim`` 可执行文件
   * - ``crates/*/tests/``
     - 拓扑渲染、会话生命周期与 vfio-user 集成测试
     - 需要 QEMU/gem5 的用例标记为 ``--ignored``
   * - ``resources/vhosts/``、``resources/devices/``
     - 可复用的 vHost 与设备模型配置
     - 由机器配置导入
   * - ``resources/machines/``、``resources/clusters/``
     - 完整机器配置与多机组合
     - 测试加载配置并渲染全部进程
   * - ``samples/``
     - 预留给 vHost 启动后运行的示例程序
     - 拓扑 YAML 存放在 ``resources/``
   * - ``scripts/``
     - 构建、开发容器、launcher、测试运行器与镜像辅助脚本
     - ``cosim_launch.sh`` 是遗留 shell launcher
   * - ``scripts/ci/``
     - CI 生命周期、ROCm 回归、镜像与运行时产物工具
     - 见 ``justfile`` 的 ``ci-*`` 与 ``scripts/ci/test_*.py`` recipe
   * - ``resources/images/recipes/``
     - 客户机镜像 recipe（Packer 模板与 Ansible playbook）
     - 唯一 recipe：``ubuntu/24.04/x86_64/rocm/7.0/``
   * - ``third_party/gem5/src/dev/amdgpu/``
     - MI300X 设备模型、vfio-user 服务端、GART/PM4/SDMA/IH
     - gem5 子模块内容
   * - ``third_party/gem5/configs/example/gpufs/``
     - cosim gem5 配置
     - ``mi300_cosim.py`` 由设备适配器调用
   * - ``configs/sst/``
     - SST 网络实验数据模型
     - 独立于 Rust launcher
   * - ``ext/libvfio-user/``
     - vfio-user 传输库
     - gem5 子模块依赖
   * - ``third_party/qemu/hw/remote/vfio-user-obj.c``、``third_party/qemu/hw/vfio-user/``
     - QEMU 的 vfio-user 服务端与客户端实现
     - QEMU 子模块内容
   * - ``docs/``
     - 双语文档源
     - 中文为主，英文为逐文件镜像

构建产物
--------

构建 recipe 与产物的对应关系如下；版本信息见 :doc:`version_matrix`。

.. list-table::
   :header-rows: 1

   * - 产物
     - 路径
     - recipe
   * - QEMU
     - ``build/qemu/qemu-system-<arch>``
     - ``just build-qemu``
   * - gem5
     - ``build/gem5/<arch>/VEGA_X86/gem5.opt``
     - ``just build-gem5``
   * - 客户机内核
     - ``build/rocm-local-installed/kernel``
     - ``just build-disk``
   * - 客户机磁盘
     - ``build/rocm-local-installed/disk`` （约 55 GB）
     - ``just build-disk``
   * - ROCm asset bundle
     - ``build/rocm-assets/`` （内核、磁盘、``manifest.json`` 等）
     - ``just build-rocm-assets``
   * - Rust launcher
     - ``build/cargo/{host,container}/release/cosim``
     - ``just build-cosim``
   * - 示例 GPU 程序
     - ``build/apps/<name>/<name>.default`` （默认 ``square``）
     - ``just build-gpu-app``

会话目录与运行时产物
--------------------

``cosim run`` 为每台机器创建独立目录与资源；常见路径如下。

.. list-table::
   :header-rows: 1

   * - 路径
     - 内容
     - 生命周期
   * - ``.cosim/<name>/``
     - 运行目录：``plan.json``、``options.json``、``manifest.json``、每台机器 ``layout.json``、进程 ``output.log``、串口日志与 ``verdict.json``
     - 正常结束保留；``cosim clean <run-dir>`` 清理异常退出后的资源
   * - ``<run-dir>/session.lock``
     - 会话锁；launcher 与所有子进程持有同一把锁
     - 进程全部退出后释放
   * - ``/dev/shm/cosim-<name>-<hash>``
     - Linux 上的内存池目录，每台机器一个 ``pool`` 文件；其他系统使用 ``<run-dir>/memory``
     - 正常结束删除
   * - ``<run>/<machine>/<device>.sock``
     - 设备提供给 host 的 vfio-user socket
     - 结束删除
   * - ``<run>/<machine>/``
     - 每台机器的 qcow2 磁盘 overlay（``<disk>.qcow2``）
     - 结束删除
   * - ``~/.cache/cosim-gpu/disk-locks``
     - 共享的磁盘镜像租约锁目录（``COSIM_DISK_LOCK_DIR``）
     - 锁文件在会话结束后保留
   * - ``artifacts/standalone/<run-id>/``
     - 遗留 shell launcher 捕获的诊断产物目录
     - 由 launcher 清理流程管理

客户机镜像内文件
----------------

客户机镜像由唯一的 recipe 构建，驱动初始化依赖以下文件。

.. list-table::
   :header-rows: 1

   * - 路径（客户机内）
     - 用途
   * - ``/root/roms/mi300.rom``
     - VGA BIOS ROM 二进制，由 ``dd`` 写入 ``0xC0000``
   * - ``/usr/lib/firmware/amdgpu/mi300_discovery``
     - IP discovery 固件
   * - ``/usr/lib/firmware/amdgpu/ip_discovery.bin``
     - 指向 ``mi300_discovery`` 的符号链接
   * - ``/lib/systemd/system/cosim-gpu-initialize.service``
     - 开机初始化服务单元
   * - ``/usr/local/bin/cosim-gpu-initialize.sh``
     - 初始化脚本：写 ROM、链接固件、加载驱动并校验
   * - ``/lib/modules/$(uname -r)/updates/dkms/amdgpu.ko.zst``
     - ROCm 7.0 DKMS amdgpu 内核模块

gem5 MI300X 模型源码
--------------------

.. list-table::
   :header-rows: 1

   * - 文件（``third_party/gem5/src/dev/amdgpu/``）
     - 作用
   * - ``mi300x_vfio_user.{cc,hh}``
     - vfio-user 服务端 SimObject，导出 BAR、配置空间与中断
   * - ``MI300XVfioUser.py``
     - vfio-user SimObject 的 Python 封装
   * - ``cosim_bridge.hh``
     - vfio-user 服务端使用的 CosimBridge 抽象接口
   * - ``amdgpu_device.cc``
     - GPU 设备核心：``readROM()``、``intrPost()``、``writeFrame()``
   * - ``amdgpu_vm.{cc,hh}``
     - GART、AGP、MMHUB 与用户上下文翻译，含共享 VRAM 回退
   * - ``pm4_packet_processor.{cc,hh}``
     - PM4 解码、DMA 路由、VRAM 写路由与 ``isVRAMAddress()``
   * - ``pm4_defines.hh``
     - PM4 操作码，包括 ``IT_ACQUIRE_MEM`` 与 ``IT_SET_RESOURCES``
   * - ``sdma_engine.{cc,hh}``
     - SDMA 执行、rptr 回写路由与 ``sdma_delay`` 参数
   * - ``interrupt_handler.cc``
     - IH ring DMA 与 MSI-X 中断发送
   * - ``amdgpu_nbio.cc``
     - ASIC 初始化完成寄存器

gem5 配置、Python 组件与 QEMU 接口
----------------------------------

.. list-table::
   :header-rows: 1

   * - 文件
     - 作用
   * - ``third_party/gem5/configs/example/gpufs/mi300_cosim.py``
     - vfio-user cosim 系统配置，由 ``gem5-mi300x`` 适配器启动
   * - ``src/python/third_party/gem5/components/devices/gpus/amdgpu.py``
     - MI300X 设备定义
   * - ``third_party/qemu/hw/remote/vfio-user-obj.c``
     - QEMU 设备服务端的 vfio-user 对象实现

路径相关环境变量
----------------

.. list-table::
   :header-rows: 1

   * - 变量
     - 作用
     - 默认值
   * - ``COSIM_WORKSPACE``
     - 工作区根目录，资源路径的解析基准
     - 仓库根目录（由 ``scripts/host/dev.sh`` 设置）
   * - ``COSIM_DISK_LOCK_DIR``
     - 磁盘镜像租约锁目录
     - ``~/.cache/cosim-gpu/disk-locks``
   * - ``COSIM_ENV``
     - 构建与检查 recipe 在主机还是临时容器中执行
     - Linux 为 ``host``，其他系统为 ``container``
   * - ``COSIM_DEV_IMAGE``
     - 开发容器镜像名
     - ``cosim-dev:local``
   * - ``COSIM_HOST_ARCH``
     - 构建与执行架构
     - 当前主机架构，``x86_64`` 或 ``aarch64``
   * - ``GEM5_BUILD_DIR``
     - gem5 构建目录
     - ``build/gem5/<arch>/VEGA_X86``
   * - ``COSIM_STDIN_LIFELINE``
     - 标准输入关闭时结束会话
     - ``scripts/host/dev.sh`` 设为 ``1``
   * - ``COSIM_RUN_ID``
     - 遗留 shell launcher 的会话标识，用于派生 socket 与共享内存名
     - 由 ``scripts/host/cosim_launch.sh`` 生成
   * - ``GPU_APP_BUILD_IMAGE``
     - 客户机 GPU 测试程序的编译镜像
     - ``ghcr.io/third_party/gem5/gpu-fs:latest``

来源与维护
----------

路径与文件清单来自仓库当前布局；新增或移动文件时同步更新本页：

- 构建产物路径由 ``justfile`` 与 ``scripts/host/build.sh`` 决定。

- 会话路径与保留名由 ``crates/cosim-runtime/src/layout.rs`` 决定。

- 客户机文件路径由镜像 recipe 的 ``provision.yml`` 与 ``files/`` 决定。

- 环境变量由 ``justfile``、``scripts/host/dev.sh``、``scripts/host/cosim_launch.sh`` 与 ``crates/cosim-runtime/src/env.rs`` 定义。

核对命令：

.. code-block:: bash

   just --list
   just build-status
   just run-topology resources/machines/single-gpu.yaml --dry-run

相关页面
--------

- 版本、镜像 tag 与 provenance：:doc:`version_matrix`

- 客户机驱动参数：:doc:`guest_parameters`

- 遗留 shell launcher 参数：:doc:`legacy_launcher_flags`

- 安装与构建：:ref:`gs-install`

- 会话生命周期：:ref:`launcher-session-lifecycle`

- 会话排错与 verdict：:ref:`launcher-debugging-sessions`

- CI 与产物复用：:ref:`contrib-ci`

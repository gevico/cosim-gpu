.. SPDX-License-Identifier: Apache-2.0

.. _launcher-legacy:

遗留 shell launcher
====================

本页说明遗留 shell 启动路径的定位、运行流程和与 Rust launcher 的差异。新工作应使用 Rust launcher，本页内容只用于维护和手工调试。

定位
-----

``scripts/host/cosim_launch.sh``\ 是早期的一键启动脚本，入口 recipe 为 ``just run-launch``\ 。它面向单台客户机：gem5 在 Docker 容器中只运行 GPU 模型，QEMU 在宿主机上使用 KVM 运行客户机，两者通过标准 vfio-user 协议连接的 Unix socket 通信。

- gem5 使用 ``cosim-dev:local``\ 镜像，默认二进制为 ``build/gem5/<native>/VEGA_X86/gem5.opt``\ ，配置为 ``third_party/gem5/configs/example/gpufs/mi300_cosim.py``\ 。
- QEMU 优先使用 ``build/qemu/qemu-system-x86_64``\ ，否则回退到 ``PATH``\ 中的系统 QEMU。
- 每次运行生成 ``COSIM_RUN_ID``\ ，socket、共享内存和 screen 日志都带该 ID，减少并发运行冲突。
- 客户机内核与磁盘默认取自 ``build/rocm-local-installed/kernel``\ 和 ``disk``\ 。

与 Rust launcher 的差异
------------------------

.. list-table::
   :header-rows: 1

   * - 维度
     - Rust launcher
     - 遗留 shell launcher
   * - 输入
     - YAML 拓扑与 vHost 文档
     - 命令行参数加固定的构建产物路径
   * - 设备模型
     - 适配器选择，每进程一个 GPU
     - ``mi300_cosim.py``\ ，可用 ``--num-gpus``\ 在单进程内启用多 GPU
   * - 进程管理
     - 就绪探测、租约、信号升级、verdict
     - shell、screen、Docker 与手工清理
   * - 记录
     - ``.cosim/<name>``\ 下的结构化文件
     - ``/tmp``\ 下带 run id 的会话文件与 screen 日志
   * - 定位
     - 开发与 CI 的默认路径
     - 手工调试与旧脚本兼容

运行流程
---------

1. 准备构建产物：``just dev-image``\ 、``just build-qemu``\ 和 ``just build-gem5``\ 。
2. 生成 run id，并据此命名 socket、``/dev/shm``\ 共享内存、screen 会话和日志。
3. 启动 gem5 容器，等待 vfio-user socket 就绪。
4. 在宿主机启动 QEMU，加载内核与磁盘，并把 GPU 作为 vfio-user 客户端连接。
5. 在 screen 会话中观察客户机串口；``cosim-gpu-initialize.service``\ 在客户机内完成 ROM 写入与驱动加载。
6. 结束运行并清理容器、socket、共享内存和 screen 会话；异常残留可以用 ``just run-preflight``\ 列出、用 ``just run-clean-orphans``\ 删除。

常用命令
---------

.. code-block:: bash

   # 使用默认参数启动
   just run-launch
   # 打开 gem5 调试标志
   just run-launch --gem5-debug MI300XCosim
   # 在单个 gem5 进程中启动两个 GPU 实例
   just run-launch --num-gpus 2
   # 列出脚本的全部参数
   ./scripts/host/cosim_launch.sh --help
   # 查看并清理遗留的 socket、共享内存和容器
   just run-preflight
   just run-clean-orphans

维护边界
---------

- 脚本的参数表以 :ref:`ref-legacy-launcher` 为准，本页不重复维护默认值和逐项说明。
- 新的拓扑、设备和自动化测试应使用 Rust launcher；本脚本只做兼容性维护。
- ``mi300_cosim.py``\ 的选项（``--num-gpus``\ 、``--xgmi-topology``\ 、``--shmem-path``\ 等）属于 gem5 配置，不是 YAML 适配器契约。

源码与依据
-----------

- 启动脚本：``scripts/host/cosim_launch.sh``\ 、``scripts/host/cosim_lib.sh``\ 。
- 预检脚本：``scripts/host/cosim_preflight.sh``\ 。
- gem5 配置：``third_party/gem5/configs/example/gpufs/mi300_cosim.py``\ 。
- just recipe：``justfile``\ 中的 ``run-launch``\ 、``run-preflight``\ 和 ``run-clean-orphans``\ 。

相关页面
---------

- :doc:`index`\ ：Rust launcher 的总体介绍。
- :doc:`cli`\ ：Rust launcher 的命令与选项。
- :ref:`ref-legacy-launcher`\ ：遗留脚本参数的唯一事实源。

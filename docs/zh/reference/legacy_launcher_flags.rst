.. SPDX-License-Identifier: Apache-2.0

.. _ref-legacy-launcher:

遗留 launcher 参数表
====================

本页是 shell launcher ``scripts/host/cosim_launch.sh`` 与 gem5 cosim 配置参数的唯一事实源，取值以当前脚本与 ``mi300_cosim.py`` 为准，并修正了旧文档中过期的默认值。

适用范围
--------

``scripts/host/cosim_launch.sh`` 通过 ``just run-launch`` 调用，启动一个客户机、一个 gem5 容器并通过 vfio-user 连接；``just test-gpu`` 与 ``scripts/host/run_cosim_tests.sh`` 也使用该路径。当前文档主路径是 YAML launcher，两者不要混用参数：本页表格只描述 shell launcher 与其调用的 gem5 配置。

shell launcher 参数
-------------------

以下默认值是脚本中的生效值。``--socket-path`` 的帮助文本写的是 ``/tmp/gem5-mi300x.sock``，但脚本实际总是把运行标识拼入路径，因此默认值带 ``-<run-id>`` 后缀。

.. list-table::
   :header-rows: 1

   * - 参数
     - 生效默认值
     - 说明
   * - ``--disk-image PATH``
     - ``build/rocm-local-installed/disk``
     - 客户机磁盘镜像
   * - ``--kernel PATH``
     - ``build/rocm-local-installed/kernel``
     - 客户机 vmlinux
   * - ``--qemu-bin PATH``
     - ``build/qemu/qemu-system-x86_64``，否则 ``PATH`` 中的 ``qemu-system-x86_64``
     - QEMU 二进制
   * - ``--gem5-bin PATH``
     - ``build/gem5/<arch>/VEGA_X86/gem5.opt``
     - gem5 二进制
   * - ``--gem5-docker IMAGE``
     - ``cosim-dev:local``
     - 运行 gem5 的容器镜像
   * - ``--socket-path PATH``
     - ``/tmp/gem5-mi300x-<run-id>.sock``
     - vfio-user socket；多 GPU 时派生 ``<stem>-<n>.sock``
   * - ``--host-mem SIZE``
     - ``8G``
     - 客户机 RAM
   * - ``--host-cpus N``
     - ``4``
     - 客户机 vCPU 数量
   * - ``--vram-size SIZE``
     - ``16GiB``
     - GPU VRAM 大小
   * - ``--num-cus N``
     - ``40``
     - GPU 计算单元数量
   * - ``--gem5-debug FLAGS``
     - 无
     - 传给 gem5 的 ``--debug-flags``
   * - ``--qemu-trace EVENTS``
     - 无
     - QEMU trace events
   * - ``--share-dir PATH``
     - 无
     - 通过 9p 共享给客户机的目录，挂载 tag 为 ``cosim_share``
   * - ``--num-gpus N``
     - ``1``
     - GPU 实例数；多 GPU 使用单个 gem5 进程内的多 GPU 模式
   * - ``--timeout SECS``
     - ``120``
     - gem5 初始化超时
   * - ``--force-clean``
     - 关闭
     - 列出孤儿 cosim 资源（dry-run）
   * - ``--confirm``
     - 关闭
     - 与 ``--force-clean`` 一起真正删除孤儿资源
   * - ``-h`` / ``--help``
     - —
     - 打印帮助

派生路径与命名
--------------

运行标识由时间戳与 4 字节随机十六进制组成，下列路径都从它派生：

.. list-table::
   :header-rows: 1

   * - 路径或名称
     - 含义
     - 说明
   * - ``<YYYYmmdd-HHMMSS>-<8 hex>``
     - 运行标识（``COSIM_RUN_ID``）
     - 所有派生路径的来源
   * - ``gem5-cosim-<run-id>``
     - gem5 容器名
     - ``docker logs`` 与 ``docker exec`` 使用
   * - ``/tmp/cosim-<run-id>.session``
     - 会话目录与 ``resources.manifest``
     - 清理与诊断
   * - ``/tmp/cosim-<run-id>.log``
     - QEMU 控制台的 screen 日志
     - 失败时复制到诊断产物
   * - ``/dev/shm/cosim-guest-ram-<run-id>``
     - 客户机 RAM 共享内存文件
     - launcher 创建和删除
   * - ``/dev/shm/mi300x-vram-<run-id>``
     - 单 GPU 的 VRAM 共享内存文件
     - launcher 创建和删除
   * - ``/dev/shm/mi300x-vram-<run-id>-<n>``
     - 多 GPU 时每个 GPU 的 VRAM 共享内存文件
     - ``--num-gpus`` 大于 1 时使用
   * - ``artifacts/standalone/<run-id>/``
     - 失败时捕获的诊断产物目录
     - 含 gem5 日志、容器 inspect、控制台日志等

gem5 config 参数
----------------

``third_party/gem5/configs/example/gpufs/mi300_cosim.py`` 自身也接受一组参数；YAML 设备适配器只使用其中一部分（见 :doc:`device_adapters`），下表是配置脚本的完整默认值。

.. list-table::
   :header-rows: 1

   * - 参数
     - 默认值
     - 说明
   * - ``--socket-path``
     - ``/tmp/gem5-mi300x.sock``
     - 单 GPU 的 vfio-user socket；多 GPU 时作为基础路径
   * - ``--shmem-path``
     - ``/mi300x-vram``
     - VRAM 的 POSIX 共享内存名；多 GPU 时作为基础名
   * - ``--shmem-host-path``
     - ``/cosim-guest-ram``
     - 客户机 RAM 的 POSIX 共享内存名
   * - ``--dgpu-mem-size``
     - ``16GiB``
     - VRAM 大小
   * - ``--mem-size``
     - ``8GiB``
     - 客户机 RAM 大小
   * - ``--num-compute-units``
     - ``40``
     - 计算单元数量
   * - ``--num-gpus``
     - ``1``
     - 单个进程内的 GPU 实例数
   * - ``--shared-pool``
     - ``""``
     - YAML launcher 使用的现成内存池文件；设置后覆盖共享内存参数
   * - ``--pool-vram-offset``
     - ``0``
     - VRAM 在内存池文件中的字节偏移
   * - ``--host-memory-ranges``
     - 无
     - 客户机 RAM 区间 JSON，由 YAML launcher 传入
   * - ``--xgmi-topology``
     - 无
     - ``mesh`` 或 ``ring``，要求 ``--num-gpus`` 不小于 2
   * - ``--xgmi-bandwidth``
     - ``128GB/s``
     - xGMI 单链路带宽
   * - ``--xgmi-latency``
     - ``100ns``
     - xGMI 单跳延迟

多 GPU 的进程内模式仅由该配置脚本与 shell launcher 暴露；YAML 适配器固定 ``--num-gpus=1``。

与 YAML launcher 的差异
-----------------------

.. list-table::
   :header-rows: 1

   * - 能力
     - shell launcher
     - YAML launcher
   * - 启动单位
     - 一个客户机、一个 gem5 容器（1 到 N 个 GPU）
     - 一个拓扑文档，可含多台机器
   * - 启动命令
     - ``just run-launch``
     - ``just run-topology``
   * - 输入
     - 命令行参数 + 固定磁盘与内核路径
     - 一份拓扑 YAML，其中包含每台机器的 vHost
   * - 多 GPU
     - ``--num-gpus N``，单个 gem5 进程内多 GPU
     - 每个 GPU 一个设备进程
   * - gem5 调试标志
     - ``--gem5-debug FLAGS``
     - 设备 ``args.gem5_debug_flags``
   * - QEMU trace
     - ``--qemu-trace EVENTS``
     - 无对应字段；可在 host ``args`` 中追加 QEMU 参数
   * - 宿主机目录共享
     - ``--share-dir PATH`` （9p）
     - 无内建字段；可在 host ``args`` 中自行添加
   * - SSH 访问
     - 端口转发到 2222，客户机控制台自动登录
     - 由镜像与 host 配置决定
   * - 失败分类与诊断产物
     - 会话目录、screen 日志与 ``artifacts/standalone/<run-id>/``
     - ``verdict.json`` 与 ``[COSIM_VERDICT]`` 行

来源与维护
----------

参数定义的来源：

- ``scripts/host/cosim_launch.sh``：参数解析、默认值、派生路径与容器启动。

- ``scripts/host/cosim_lib.sh``：运行标识、容器名、socket、共享内存、会话目录与诊断产物路径。

- ``third_party/gem5/configs/example/gpufs/mi300_cosim.py``：gem5 侧参数与默认值。

- ``justfile``：``run-launch`` 与 ``test-gpu`` 入口。

核对帮助文本与实际默认值：

.. code-block:: bash

   scripts/host/cosim_launch.sh --help
   just run-launch --force-clean

相关页面
--------

- 遗留 launcher 的使用流程：:ref:`launcher-legacy`

- 版本、镜像与 provenance：:doc:`version_matrix`

- 文件与会话路径：:doc:`files_and_artifacts`

- 客户机参数：:doc:`guest_parameters`

- 相关已知问题：:doc:`known_issues`

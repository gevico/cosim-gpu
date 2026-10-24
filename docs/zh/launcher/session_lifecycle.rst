.. SPDX-License-Identifier: Apache-2.0

.. _launcher-session-lifecycle:

会话生命周期
=============

本页说明 ``cosim run``\ 从发布会话目录到写 verdict 的完整生命周期，重点是进程顺序、就绪探测、租约、信号、磁盘 overlay 和资源清理。

启动顺序
---------

.. mermaid::

   sequenceDiagram
       participant L as Launcher
       participant D as Device process
       participant H as Host QEMU
       L->>D: start
       D->>D: readiness probes
       D->>H: lease
       L->>H: start when all leases are held
       H->>H: QMP and serial probes
       Note over L,H: running
       L-->>H: cancellation, run-for deadline or host exit
       H->>H: shutdown
       H-->>D: release lease
       D->>D: shutdown after the last lease is released
       L->>L: remove overlays and pools, write verdict

运行目录与资源发布
-------------------

- 运行目录先以临时名称创建，持有 ``session.lock``\ ，并完整写入 ``manifest.json``\ 、``plan.json``\ 和 ``options.json``\ 。
- 创建外部资源之前，通过一次重命名发布运行目录，因此读到的会话目录总是完整元数据。
- 随后创建内存池目录，为每台机器预留内存池容量，并准备磁盘。
- 内存池目录先以临时名称创建并写入所有权标记，再以不替换已有目录的方式重命名到正式位置，因此该目录出现时一定带有标记。
- 启动器在启动任何模拟器之前预留共享内存容量；并发会话共享文件系统可用容量，预留失败时释放该会话的资源。

进程监督与就绪探测
-------------------

- 进程在全部依赖就绪后启动；每个设备排在它的 host 之前，host 依赖本机的全部设备。不同机器之间互不等待。
- 探测按顺序进行：输出日志标记、Unix socket 存在、QMP 协商；host 还等待 ``serial.wait_for``\ 指定的串口标记。
- 每个探测必须在进程启动后 ``--ready-timeout``\ 内成功；设置了 ``serial.timeout``\ 时，串口标记使用该时限。
- 就绪的设备交给每个依赖者一个租约，最后一个租约释放后才停止，因此 host 总是先于设备停止。

关闭与信号
-----------

- host 以状态 0 退出时结束本机；其他退出、探测失败或磁盘准备失败会取消整个会话。
- 磁盘准备期间收到取消请求会停止 ``qemu-img``\ ，会话正常结束，不记录失败。
- 第一个 SIGINT 或 SIGTERM 开始有序关闭，后续信号跳过剩余等待时间。
- ``--run-for``\ 在全部进程就绪后限定运行时长；``--stdin-lifeline``\ （开发容器会设置）在标准输入关闭时结束会话。
- 每个进程组先收到 SIGTERM，有 5 秒退出时间，然后收到 SIGKILL。子进程通过 ``setpriv --pdeathsig KILL``\ 启动，随 launcher 一起结束。
- ``cosim run``\ 依赖使用 glibc 的 Linux 和 ``setpriv``\ 。

开发容器中的会话
-----------------

构建、运行拓扑和 Rust 检查的 recipe 通过 ``scripts/host/dev.sh``\ 执行。依赖齐全时它们在 Linux 上原生运行；其他系统，或设置了 ``COSIM_ENV=container``\ 的 Linux，会使用临时开发容器。

- 源码树按宿主机路径挂载，``COSIM_WORKSPACE``\ 指向仓库根目录，因此 YAML、执行计划和日志中的路径在容器内外一致。
- 容器使用自己的 ``/dev/shm``\ ，大小上限取决于 Docker daemon 的内存；内存池随容器一起消失。存在 ``/dev/kvm``\ 时会传入容器。
- 除 ``--tty``\ 模式外，``dev.sh``\ 在 Docker 客户端运行期间保持容器标准输入打开，并设置 ``COSIM_STDIN_LIFELINE=1``\ ；客户端消失时 launcher 随之停止。
- launcher 无论以何种方式退出，容器 init 进程都会退出，内核随后终止容器内剩余进程，因此不会留下孤儿子进程。
- ``just dev-shell``\ 可以在临时容器中打开 shell，容器名为 ``cosim-dev-<random>``\ ，可用 ``docker exec``\ 进入。

磁盘、overlay 与锁
-------------------

- ``readonly: true``\ 以只读方式打开源镜像；``readonly: false``\ 要求同时写 ``shared: false``\ ，并直接写入 ``path``\ 。
- 磁盘声明 ``backing``\ 或 vHost 设置 ``snapshot: true``\ 时，改为在会话目录中为每台机器写入一个 qcow2 overlay。
- 未写出 ``readonly``\ 的磁盘同样为每台机器写入一个 qcow2 overlay；``shared: true``\ 要求 ``readonly: true``\ 。
- ``create: true``\ 加 ``size``\ 使用 ``qemu-img``\ 创建缺失镜像：先以临时名称格式化，再通过链接发布，不会替换其他会话同时创建的镜像。
- 磁盘锁目录由 ``COSIM_DISK_LOCK_DIR``\ 指定，默认 ``~/.cache/cosim-gpu/disk-locks``\ 。锁文件在会话结束后仍然保留，因此锁目录必须位于内存池目录之外。
- 镜像租约按设备号和 inode 区分；只要 launcher，或者可能使用该镜像的 host 或辅助进程还存活，租约就持续有效。

清理与会话记录
---------------

- 全部进程停止后删除 socket、overlay、内存池和内存池目录，日志保留。
- 无法确认进程已经终止时保留资源，并在 ``verdict.json``\ 中记录 ``users_stopped: false``\ 。
- launcher 被杀死或异常退出后，``cosim clean <run-dir>``\ 删除 ``manifest.json``\ 中列出的资源；只有 launcher 及其全部进程都已退出并释放 ``session.lock``\ 后才执行。
- ``clean``\ 只从所有权标记属于本会话的内存池目录中删除内存池；其他会话以同一名称发布的目录保持不变。

.. list-table::
   :header-rows: 1

   * - 会话文件
     - 内容
   * - ``plan.json``
     - 执行的计划：程序、参数、环境、依赖、探测和内存区域。
   * - ``options.json``
     - 本次运行的选项：就绪超时、运行时长和 ``qemu-img``\ 等。
   * - ``manifest.json``
     - ``clean``\ 可以删除的资源清单。
   * - ``<machine>/layout.json``
     - 每台机器的内存区域名称、偏移和大小。
   * - ``<machine>/<node>/output.log``
     - 进程标准输出与标准错误的合并日志。
   * - ``<machine>/vhost/serial.log``
     - host QEMU 的串口日志。
   * - ``verdict.json``
     - 最终结果；同时由 ``[COSIM_VERDICT]``\ 行输出。

源码与依据
-----------

- 会话执行与 verdict：``crates/cosim-runtime/src/session.rs``\ 。
- 进程节点、依赖与探测：``crates/cosim-runtime/src/node.rs``\ 、``probe.rs``\ 。
- 资源所有者与锁：``crates/cosim-runtime/src/resource.rs``\ 、``process.rs``\ 。
- 磁盘准备与 overlay：``crates/cosim-runtime/src/disk.rs``\ 。
- 清理：``crates/cosim-runtime/src/manifest.rs``\ 。

相关页面
---------

- :doc:`yaml_pipeline`\ ：计划是如何生成的。
- :doc:`debugging_sessions`\ ：从日志和 verdict 定位失败。
- :ref:`arch-execution-flow`\ ：会话执行流程的系统视图。
- :ref:`arch-memory-model`\ ：内存池与共享内存模型。
- :ref:`gs-platform-container`\ ：开发容器的环境与限制。
- :ref:`ref-files-and-artifacts`\ ：会话目录、构建产物与锁目录。

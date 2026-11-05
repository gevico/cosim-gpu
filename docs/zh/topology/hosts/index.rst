.. SPDX-License-Identifier: Apache-2.0


.. _topo-vhosts:

vHost 配置
==========

每台机器有一个 QEMU vHost 进程。vHost 模板把 YAML 字段渲染成 QEMU 命令行，绑定内存池，并暴露 QMP 与串口。本页说明 vHost 在拓扑中的位置、字段、随仓库提供的 6 个 profile，以及 QEMU 命令契约、内存映射与串口就绪。完整字段表见 :ref:`ref-topology-schema`\ ，适配器实现位于 ``crates/cosim-topology/src/adapter/mod.rs``\ 。

vHost 在拓扑中的位置
---------------------

- 一台机器恰好一个 vHost；其 kind 必须使用 ``model: qemu``，仓库只提供 ``qemu-vhost``\ 。
- ``resources/vhosts/qemu.yaml`` 声明 ``qemu-vhost``\ ：命令模板用 MiniJinja 渲染，绑定内存池，提供 QMP 与串口，先为每个设备在槽位 ``0x10`` 到 ``0x17`` 分配独立 PCIe root port（8 个 function），再由 QEMU 把磁盘放到剩余槽位。
- kind 声明 ``max_devices: 64``\ ；一台机器的设备数量不能超过该值。
- vHost 必须在全部本机设备就绪并交出租约后才能启动；vHost 关闭后设备才停止。
- vHost 程序必须在前台运行、把资源使用者保留在自己的进程组中并保持继承的文件描述符打开；QEMU ``-daemonize`` 会被拒绝。

vHost 字段
----------

.. list-table::
   :header-rows: 1

   * - 字段
     - 类型
     - 默认
     - 说明
   * - ``kind``
     - string
     - 无
     - 必须解析为 ``model: qemu`` 的 vHost kind
   * - ``runtime.binary``
     - path 或名称
     - 无
     - 相对工作区根目录；不含 ``/`` 时从 ``PATH`` 查找
   * - ``runtime.env``
     - map
     - ``{}``
     - 进程只额外获得 ``PATH`` 与 ``LANG=C``
   * - ``memory``
     - 字节大小
     - 无
     - 必须是执行系统页大小的整数倍
   * - ``cpus``
     - 正整数
     - 无
     - 传给 QEMU 的 ``-smp``
   * - ``accel``
     - string
     - 无
     - 例如 ``kvm`` 或 ``tcg``
   * - ``machine``
     - string
     - 无
     - QEMU machine 类型，例如 ``q35``
   * - ``cpu``
     - string
     - 无
     - 传给 ``-cpu``
   * - ``display``\ 、``monitor``
     - string
     - 无
     - QEMU 后端；样例使用 ``none``
   * - ``no_reboot``
     - bool
     - ``false``
     - 添加 ``-no-reboot``
   * - ``memory_align``
     - 字节大小
     - 2 MiB
     - 2 的幂，也是设备区域的默认对齐
   * - ``memory_map``
     - MiniJinja 模板
     - 无
     - 含 gem5-mi300x 设备时必需
   * - ``serial.wait_for``\ 、``serial.timeout``
     - string、1 到 86400 秒
     - 无、会话的 ``--ready-timeout``
     - 串口就绪标记与截止时间
   * - ``args``
     - list
     - ``[]``
     - 追加到 QEMU 命令行末尾

内置 profile
------------

6 个 profile 定义在 ``resources/vhosts/`` 中，机器通过 ``use`` 选择。

.. _topo-vhost-x86:

vhost-x86
~~~~~~~~~

- ``q35``\ 、``kvm``\ 、``host`` CPU、8 GiB RAM、4 vCPU；二进制为 ``build/qemu/qemu-system-x86_64``\ 。
- ``memory_map`` 描述 x86_64 PCI 空洞：RAM 不小于 2.75 GiB 时，4 GiB 以下保留 2 GiB，其余放到 4 GiB 以上。
- 提供 x86_64 KVM 的基础运行参数，镜像和启动输入由使用它的 vHost 配置声明。

.. _topo-vhost-x86-rocm:

vhost-x86-rocm
~~~~~~~~~~~~~~

- 继承 ``vhost-x86``，通过 ``image`` 选择 ``ubuntu/24.04/x86_64/rocm/7.0`` 配方。
- 配置 virtio 启动盘，以及串口、根文件系统和 ``modprobe.blacklist=amdgpu`` 内核参数。
- ``single-gpu``、``gpu-8`` 和 ``mixed-models`` 使用该 profile 启动 ROCm 客户机。
- 配方定义软件安装与产物；此 profile 定义仿真会话的启动设置。

.. _topo-vhost-arm:

vhost-arm
~~~~~~~~~

- ``virt,gic-version=3``\ 、``kvm``\ 、``host`` CPU、8 GiB RAM、4 vCPU；二进制为 ``build/qemu/qemu-system-aarch64``\ 。
- ``memory_map`` 把 RAM 放在 1 GiB。
- 没有样例直接使用该 KVM profile；它只作为 ``vhost-arm-tcg`` 的基础模板。

.. _topo-vhost-riscv:

vhost-riscv
~~~~~~~~~~~

- ``virt,aia=aplic-imsic``、``tcg``、``rva23s64,sv48=on`` CPU、4 GiB RAM、
  2 vCPU；二进制为 ``build/qemu/qemu-system-riscv64``。
- ``memory_map`` 把 RAM 放在 2 GiB（``0x80000000``），共享池偏移从零开始；
  设备后端接收对应的来宾物理地址范围。

.. _topo-vhost-x86-tcg:

vhost-x86-tcg
~~~~~~~~~~~~~

- 继承 ``vhost-x86``\ ，覆盖为 ``tcg``\ 、``qemu64``\ 、64 MiB RAM、1 vCPU。
- 二进制写裸名 ``qemu-system-x86_64``\ ，生成计划时从 ``PATH`` 查找。
- ``args`` 为 ``[-S, -nodefaults]``\ ，vHost 启动后保持暂停，用于不启动操作系统的会话测试。

.. _topo-vhost-arm-tcg:

vhost-arm-tcg
~~~~~~~~~~~~~

- 继承 ``vhost-arm``\ ，覆盖为 ``tcg``\ 、``cortex-a72``\ 、64 MiB RAM、1 vCPU。
- 二进制写裸名 ``qemu-system-aarch64``\ ；``args`` 为 ``[-S, -nodefaults]``\ 。
- AArch64 样例与架构相关会话测试使用该 profile。

QEMU 命令契约
-------------

vHost kind 用命令模板生成 QEMU 参数，模板上下文包括 ``vhost``\ 、``machine``\ 、
``pool``\ 、``ram``\ 、``guest_ranges``\ 、``boot``\ 、``disks``\ 、``devices``\ 、
``qmp``\ 、``serial``\ 、``serial_log``\ 、``cmdline``\ 、``run_dir`` 与 ``node_dir``\ 。

- ``-machine <machine>,memory-backend=ram``\ 、``-accel``\ 、``-m``\ 、``-smp``\ ；
- ``memory-backend-file``\ （``share=on``\ ，offset 为客户机 RAM 偏移）绑定内存池；
- QMP Unix socket；串口 chardev 加 logfile；
- 可选 ``-cpu``\ 、``-display``\ 、``-monitor``\ 、``-append``\ ；vHost 含 ``kernel`` 时加 ``-kernel`` 与 ``-initrd``\ ；``no_reboot`` 为真时加 ``-no-reboot``\ ；
- 每个设备一个 ``pcie-root-port`` 和一个 ``vfio-user-pci`` 客户端（存在 ``pci.rom`` 时带 ``romfile``\ ）；
- 有 SCSI 磁盘时加 ``virtio-scsi-pci``\ ；磁盘先渲染为 ``-blockdev`` 的 file 与 format 节点，再按 ``bus`` 映射为 ``virtio-blk-pci``\ 、``nvme``\ 、``scsi-hd`` 或 ``ide-hd``\ ，启动盘加 ``bootindex=1``\ ；
- 最后追加 ``vhost.args``\ 。

就绪探测按顺序进行：串口 socket 存在、QMP 协商成功、可选的 ``serial.wait_for`` 日志标记。模板中的未定义值会报错，而不是渲染为空。

内存映射
--------

- ``memory_map`` 是 MiniJinja 模板，接收 ``vhost`` 与 ``ram.size``\ ，渲染出 1 到
  64 个有序、互不重叠、正好覆盖 ``memory`` 的 ``{start, size}`` 区间。
- 机器含 gem5 MI300X 设备时必须提供 ``memory_map``\ ；只有 QEMU 设备时不需要。
- QEMU 通过 ``memory-backend-file`` 映射客户机 RAM；gem5 收到 ``--host-memory-ranges`` 与 ``--shared-pool``\ ，映射同一个内存池文件。地址空间细节见 :ref:`arch-memory-model`\ 。

串口与就绪时限
--------------

- ``serial.wait_for`` 增加串口就绪标记；``serial.timeout`` 以秒为单位限制该标记，从 vHost 启动时开始计时，要求同时设置 ``wait_for``\ 。
- 未设置 ``serial.timeout`` 时使用会话的 ``--ready-timeout``\ （默认 120 秒）。
- vHost 以状态 0 退出时结束本机；其他退出、探测失败或取消会结束整个会话。

相关页面
--------

- 机器目录：:doc:`../machines/index`
- 设备目录：:doc:`../devices/index`
- 编写拓扑：:doc:`../write_topology`
- 参考：:ref:`ref-topology-schema`
- 第 4 章：:ref:`sim-qemu-vhost`
- 生命周期：:ref:`launcher-session-lifecycle`
- 源码：``resources/vhosts/qemu.yaml``\ 、``resources/vhosts/vhost-x86-tcg.yaml``\ 、``resources/vhosts/vhost-arm-tcg.yaml``

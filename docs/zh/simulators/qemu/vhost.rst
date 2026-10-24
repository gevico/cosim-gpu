.. SPDX-License-Identifier: Apache-2.0

.. _sim-qemu-vhost:

QEMU 作为 vhost
================

本页说明 QEMU vHost 如何被启动：机器类型与加速器、内存池映射、PCIe 拓扑、直接内核启动、QMP 和串口，以及磁盘如何挂载。命令由 YAML vHost 模板渲染，因此字段和默认值以第 5 章的 vHost 配置与第 6 章的 schema 为准。

启动配置
---------

vHost 声明适配器 ``kind``\ 、``runtime.binary``\ 和 ``runtime.env``\ 、``memory``\ 、``cpus``\ 、``accel``\ 和 ``machine``\ ，可选字段包括 ``cpu``\ 、``display``\ 、``monitor``\ 、``no_reboot``\ 、``memory_align``\ 、``memory_map``\ 、``serial``\ 和 ``args``\ 。``resources/vhosts/qemu.yaml``\ 声明的 ``qemu-vhost``\ kind 负责把字段渲染为 QEMU 参数。

.. list-table::
   :header-rows: 1

   * - vHost 配置
     - 机器与加速器
     - 用途
   * - ``vhost-x86``
     - ``q35``\ ，``accel: kvm``\ ，``cpu: host``
     - x86_64 客户机，默认 8 GiB 内存、4 个 vCPU。
   * - ``vhost-arm``
     - ``virt,gic-version=3``\ ，``accel: kvm``
     - ARM64 客户机，内存放在 ``0x40000000``\ 。
   * - ``vhost-x86-tcg``
     - ``q35``\ ，``accel: tcg``\ ，``-S``
     - 仅 vHost 或设备模型样例，暂停启动、64 MiB 内存。
   * - ``vhost-arm-tcg``
     - ``virt``\ ，``accel: tcg``\ ，``-S``
     - ARM64 的设备模型样例。

内存与 PCIe 拓扑
-----------------

- 客户机内存通过 ``memory-backend-file``\ 映射内存池：``mem-path``\ 指向本机 pool 文件，``offset``\ 是客户机 RAM 区域偏移，``share=on``\ 允许 gem5 共享同一组字节。
- ``memory_map``\ 描述客户机物理地址区间。Q35 在内存较大时把 RAM 拆成 4 GiB 以下和 4 GiB 以上两段；AArch64 virt 从 1 GiB 开始。PCI 地址空洞不占内存池字节。
- 每个设备获得一个独立的 ``pcie-root-port``\ ，位于插槽 ``0x10``\ 到 ``0x17``\ ，每个端口 8 个功能；vHost kind 的 ``max_devices``\ 为 64。
- 设备以 ``vfio-user-pci``\ 客户端挂到对应 root port，``socket``\ 指向设备进程监听的 Unix socket；声明了 ``pci.rom``\ 时通过 ``romfile`` 提供 option ROM。
- 磁盘使用剩余的插槽，由 QEMU 自行分配。

启动、QMP 与串口
-----------------

- vHost 的 ``kernel``\ 启用直接内核启动：生成 ``-kernel``\ 和可选的 ``-initrd``\ ，``-append``\ 由 vHost 的 ``cmdline``\ 与设备 ``guest_hints.cmdline``\ 拼接。
- 默认 vHost 配置带 ``no_reboot``\ ，操作系统重启不会掩盖会话结束；``display``\ 和 ``monitor``\ 默认关闭。
- QMP socket 以 ``server=on,wait=off`` 方式创建；launcher 在启动后完成 QMP 能力协商，作为 vHost 的就绪探测之一。
- 串口通过 ``chardev`` socket 提供，并写入 ``serial.log``\ 文件；``serial.wait_for``\ 可以让 launcher 额外等待客户机输出中的就绪标记，``serial.timeout``\ 为该标记设置秒级时限。
- vHost 和设备程序必须在前台运行；``-daemonize``\ 会被 launcher 拒绝，因为它与进程组所有权冲突。

.. code-block:: text

   -machine q35,memory-backend=ram
   -accel kvm -m <ram.size>B -smp <cpus> -cpu host
   -object {"qom-type":"memory-backend-file","id":"ram","size":<ram.size>,
            "mem-path":"<pool>","offset":<ram.offset>,"share":true}
   -qmp unix:<run-dir>/m0/qmp.sock,server=on,wait=off
   -chardev socket,id=serial0,path=<run-dir>/m0/serial.sock,server=on,wait=off,logfile=<serial.log>
   -serial chardev:serial0
   -device pcie-root-port,id=rp0,bus=pcie.0,...
   -device vfio-user-pci,bus=rp0,socket={"type":"unix","path":"<device.sock>"}

磁盘
-----

.. list-table::
   :header-rows: 1

   * - ``bus``
     - QEMU 设备
     - 说明
   * - ``virtio``
     - ``virtio-blk-pci``
     - 默认总线，适合根文件系统。
   * - ``nvme``
     - ``nvme``
     - 序列号由机器与磁盘标识符组成。
   * - ``scsi``
     - ``virtio-scsi-pci``\ 加 ``scsi-hd``
     - 需要时自动追加 SCSI 控制器。
   * - ``ide``
     - ``ide-hd``
     - 兼容旧镜像。

每个磁盘先用 ``-blockdev``\ 打开文件节点，再按 ``format``\ （``raw``\ 或 ``qcow2``\ ）叠加格式节点，``read-only``\ 属性来自磁盘声明；vHost 指定 ``boot: true``\ 的磁盘获得 ``bootindex=1``\ 。

源码与依据
-----------

- vHost kind 与命令模板：``resources/vhosts/qemu.yaml``\ 。
- TCG profile：``resources/vhosts/vhost-x86-tcg.yaml``\ 、``resources/vhosts/vhost-arm-tcg.yaml``\ 。
- vHost 参数渲染与探测：``crates/cosim-topology/src/adapter/mod.rs``\ 。
- 启动 vHost：``resources/vhosts/qemu.yaml``\ 。

相关页面
---------

- :doc:`index`\ ：QEMU 的两个职责。
- :doc:`device_models`\ ：QEMU 作为 device model。
- :ref:`topo-vhosts`\ ：vHost 配置字段与策略。
- :ref:`arch-memory-model`\ ：内存池与共享内存模型。
- :ref:`gs-first-session`\ ：首次会话的完整命令。

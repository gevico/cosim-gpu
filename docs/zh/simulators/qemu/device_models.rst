.. SPDX-License-Identifier: Apache-2.0

.. _sim-qemu-device-models:

QEMU 作为 device model
=======================

本页说明如何用 QEMU 导出功能设备模型：``qemu-device``\ 适配器启动 ``-machine x-remote``\ 进程，通过 ``x-vfio-user-server``\ 把一个 PCI 设备暴露给 host QEMU。该模式只保证功能正确，不提供时序模型。

启动方式
---------

``qemu-device``\ 适配器把 ``args.device``\ 渲染成 QEMU 设备属性并启动如下形态的命令：

.. code-block:: text

   -machine x-remote,vfio-user=on,auto-shutdown=off
   -nodefaults -display none
   -qmp unix:<run-dir>/m0/<device>.qmp.sock,server=on,wait=off
   -device {"driver":"edu","id":"device0"}
   -object {"qom-type":"x-vfio-user-server","id":"vfio0",
            "socket":{"type":"unix","path":"<run-dir>/m0/<device>.sock"},
            "device":"device0"}

- ``args.device.driver``\ 必填；未写 ``id``\ 时默认为 ``device0``\ 。
- ``args.extra``\ 追加额外 QEMU 参数；``runtime.binary``\ 必须启用 vfio-user server 的 QEMU。
- 适配器不接受 ``config``\ 和私有内存区域；需要私有内存时应改用 ``role: device``\ 的命令模板 kind。
- ``auto-shutdown=off``\ 让 server 在最后一个客户端断开后仍保持运行，由 launcher 按进程组统一停止。

示例：edu 设备
---------------

``resources/devices/pci/qemu-edu.yaml``\ 使用 QEMU 自带的 ``edu``\ 教学 PCI 设备。该设备提供配置空间、BAR、DMA 和中断，足以演示 vfio-user 的配置空间、MMIO 与中断转发路径。对应机器样例是 ``resources/machines/qemu-device.yaml``\ ：一个暂停的 x86_64 TCG host 连接一个 ``edu``\ 设备。

就绪与生命周期
---------------

- 就绪探测依次为：可选的 ``ready_log``\ 日志标记、Unix socket 存在、QMP 能力协商。
- 设备先于 host 启动；host 在全部设备就绪后才启动。
- host 先停止，随后 launcher 停止设备进程；两端都有独立的 QMP 与日志。
- 设备进程没有客户机内存视图，DMA 与配置空间访问都通过 vfio-user 协议与 host 交换。

适用边界
---------

- 功能仿真：只保证设备寄存器、BAR 和中断行为正确，不模拟时序与性能。
- 适合协议验证、驱动路径验证和低成本的集成测试。
- 需要 MI300X 的命令处理、缓存或内存层次行为时，应使用 :doc:`../gem5/index`\ 的性能模型适配器。

源码与依据
-----------

- 适配器实现：``crates/cosim-topology/src/adapter/qemu_device.rs``\ 。
- 示例设备模板：``resources/devices/pci/qemu-edu.yaml``\ 。
- QEMU vfio-user server：``third_party/qemu/hw/remote/vfio-user-obj.c``\ 。
- edu 设备：``third_party/qemu/hw/misc/edu.c``\ 。

相关页面
---------

- :doc:`vhost`\ ：host QEMU 的运行环境。
- :doc:`index`\ ：QEMU 的两个职责。
- :doc:`../gem5/index`\ ：gem5 性能仿真。
- :ref:`topo-machines-qemu-device`\ ：qemu-device 机器样例。
- :ref:`ref-device-adapters`\ ：设备适配器契约。

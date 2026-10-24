.. SPDX-License-Identifier: Apache-2.0


.. _topo-machines-qemu-device:

qemu-device 机器
================

概述
----

``qemu-device`` 板卡是"暂停的 x86_64 主机 + 一个 QEMU ``edu`` 设备"：设备进程以 ``-machine x-remote`` 运行，并通过 vfio-user 把 ``edu`` PCI 设备导出给主机。它用于验证 QEMU 设备适配器、设备与主机的启动顺序、socket 与 QMP 探测，以及 option ROM 处理；板卡不启动客户机。

拓扑
----

.. code-block:: yaml

   # resources/machines/qemu-device.yaml
   version: 1
   imports:
     - vhosts/qemu.yaml
     - vhosts/vhost-x86-tcg.yaml
     - devices/pci/qemu-edu.yaml
   machines:
     - id: m0
       vhost:
         use: vhost-x86-tcg
         runtime: {binary: build/qemu/qemu-system-x86_64}
     devices:
       - {use: qemu-edu}

- 机器数量：1（``m0``\ ）；主机覆盖 ``runtime.binary``\ ，改用子模块构建的 QEMU。
- 设备使用默认标识符 ``qemu-edu-0``\ ，没有私有内存区域。
- vHost 以 ``-S -nodefaults`` 暂停启动，且没有镜像或内核。

硬件资源
--------

.. list-table::
   :header-rows: 1

   * - 资源
     - 值
     - 来源
   * - 机器
     - 1 台（``m0``\ ）
     - ``resources/machines/qemu-device.yaml``
   * - vHost 配置
     - ``vhost-x86-tcg``\ ：``q35``\ 、``tcg``\ 、``qemu64`` CPU
     - ``resources/vhosts/vhost-x86-tcg.yaml``
   * - 客户机 RAM
     - 64 MiB，1 vCPU
     - 同上
   * - 设备
     - 1 × ``qemu-edu``\ ：``args.device`` 为 ``{driver: edu}``
     - ``resources/devices/pci/qemu-edu.yaml``
   * - 内存池
     - 64 MiB（设备没有私有区域）
     - 主机 RAM
   * - 可执行文件
     - 主机与设备均为 ``build/qemu/qemu-system-x86_64``
     - 两个模板
   * - socket
     - 主机 QMP 与串口；设备 vfio-user socket 与 QMP
     - 会话布局
   * - vHost
     - 无
     - —

软件栈
------

.. list-table::
   :header-rows: 1

   * - 层
     - 组件
     - 说明
   * - 客户机 OS
     - 无
     - 主机暂停，不启动内核
   * - 设备模型
     - ``qemu-device`` 适配器
     - ``-machine x-remote,vfio-user=on,auto-shutdown=off``
   * - 设备导出
     - ``x-vfio-user-server`` 对象
     - 把 ``args.device`` 描述的 PCI 设备导出到 Unix socket
   * - 构建依赖
     - 带 vfio-user 支持的 QEMU
     - 由 ``just build-qemu`` 构建
   * - 就绪探测
     - 可选 ``ready_log``\ 、socket 存在、QMP 协商
     - 顺序见适配器契约

运行该机器
----------

.. code-block:: bash

   # 先构建带 vfio-user 支持的 QEMU
   just build-qemu
   # 校验与预览
   just run-cli validate resources/machines/qemu-device.yaml --assets
   just run-topology resources/machines/qemu-device.yaml --dry-run
   # 冒烟运行，2 秒后结束
   just run-topology-dev resources/machines/qemu-device.yaml --run-for 2

- 设备进程先启动并进入监听；主机在设备就绪后才启动。
- 关闭时主机先停止，设备在最后一个租约释放后退出。
- vfio-user 的接口细节见 :ref:`arch-vfio-user`\ ，生命周期见 :ref:`launcher-session-lifecycle`\ 。

验证
----

- 计划输出为 1 个主机进程与 1 个设备进程，设备在主机之前启动。
- 集成测试 ``vfio_user_devices_start_before_the_host_and_stop_after_it`` 覆盖这一启动与停止顺序。
- 集成测试 ``vfio_user_option_rom_is_checked_and_exposed`` 覆盖 option ROM 缺失、不可读与暴露到 ROM BAR 三种情况。
- 两个测试由 ``just test-cosim-vfio-user`` 运行，使用 ``just build-qemu`` 的产物。

限制
----

- 主机暂停，没有客户机；客户机内设备驱动路径不在本板卡覆盖范围内。
- ``edu`` 是测试设备，没有对应的客户机驱动。
- ``qemu-device`` 不接受 ``config`` 与私有内存区域，启动约定由适配器固定。
- 运行需要自建 QEMU；系统 QEMU 不保证包含 vfio-user 支持。运行会话需要 Linux glibc 与 ``setpriv``\ 。

相关页面
--------

- 设备目录：:doc:`../devices/index`
- vHost 配置：:doc:`../hosts/index`
- 机器目录：:doc:`index`
- 第 4 章：:ref:`sim-qemu-device-models`\ ，:ref:`sim-qemu-vhost`
- 适配器契约：:ref:`ref-device-adapters`
- 源码：``resources/machines/qemu-device.yaml``\ 、``resources/devices/pci/qemu-edu.yaml``

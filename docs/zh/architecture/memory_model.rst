.. SPDX-License-Identifier: Apache-2.0

.. _arch-memory-model:

内存与共享内存模型
==================

每台机器拥有一个内存池文件，客户机内存与设备区域按固定布局排布。QEMU 与
设备模型映射同一文件，从而共享客户机内存与 VRAM。

内存池与区域
------------

launcher 在启动进程前计算每台机器的布局：

- 客户机内存位于第一个区域，设备区域按声明顺序追加；
- 每个区域的大小必须是执行系统页大小的整数倍，起始对齐是不小于一页的 2 的
  幂，默认 2 MiB；
- 每个区域的名称、偏移与大小写入 ``layout.json``；
- 内存池总大小按布局一次算清，例如 8 GiB 客户机内存加一个 16 GiB VRAM 区域
  得到 24 GiB 池。

.. mermaid::

   flowchart LR
       R[guest_ram 区域] --- H[Host QEMU]
       R --- G0[gem5 设备 0]
       R --- G1[gem5 设备 1]
       V0[mi300x-0.vram 区域] --- G0
       V1[mi300x-1.vram 区域] --- G1
       V0 ---|BAR0 映射| H
       V1 ---|BAR0 映射| H

客户机物理地址与文件偏移
------------------------

vHost 模板通过 ``memory_map`` 声明客户机物理 RAM 区间。Rust 校验区间顺序、
页边界与总大小，为它们分配连续的文件偏移，再把结果通过
``--host-memory-ranges`` 传给 gem5。

.. list-table::
   :header-rows: 1

   * - vHost profile 与客户机地址区间
     - 池文件偏移
   * - Q35：``[0, below_4g)``
     - 从 0 开始
   * - Q35：``[4 GiB, 4 GiB + above_4g)``
     - 从 ``below_4g`` 开始
   * - AArch64 virt：``[1 GiB, 1 GiB + ram_size)``
     - 从 0 开始

PCI 地址空洞不占用池文件字节。VRAM 区域位于完整客户机内存之后，客户机物理
地址与文件偏移是两个独立字段。标准 x86 配置把 RAM 拆成低地址与 4 GiB 以上
两段，低地址段最多 2 GiB（RAM 不小于 2.75 GiB 时）。

QEMU 与 gem5 如何共享
---------------------

- QEMU 用 ``memory-backend-file`` 映射客户机内存区域，``share=on``，并指定
  ``offset=ram.offset``；
- gem5 的 ``PhysicalMemory`` 在指定偏移映射客户机内存与设备内存，检查区域
  大小，并保持外部文件原有长度；
- ``MI300XVfioUser`` 用与池中 VRAM 相同的文件偏移调用 ``vfu_setup_region``，
  因此 QEMU 通过 BAR0 映射访问的字节与 gem5 设备内存是同一份；
- QEMU 设备进程没有私有区域，客户机内存通过 vfio-user 的 DMA 映射提供。

VRAM 访问不走 vfio-user：它由共享文件的 BAR 映射直接完成。vfio-user 只承载
配置空间、MMIO、DMA 映射与中断。

容量预留与会话隔离
------------------

- launcher 在启动任何模拟器之前预留内存池容量；并发会话在准备阶段占用文件
  系统可用容量，预留失败时会释放该会话已占用的资源；
- Linux 上池目录默认为 ``/dev/shm/cosim-<name>-<hash>``，其他系统使用
  ``<run-dir>/memory``；目录先以临时名称创建并写入所有权标记，再以不替换
  已有目录的方式发布；
- 会话结束时删除池文件与池目录，其他会话以同名发布的目录不受影响；
- 检查运行目录与池目录的包含关系前，两个路径中已存在的部分会先解析符号链接。

数据与一致性
------------

客户机内存保存命令环、fence、中断记录、队列描述符与 DMA 缓冲；VRAM 保存
设备分配、discovery 信息与 GPU 页表。共享文件只提供数据存储，访问顺序、
缓存行为与同步语义由设备模型和客户机软件决定。地址翻译细节见
:ref:`GPU 地址翻译 <sim-gem5-address-translation>`。

相关页面
--------

- :doc:`components`
- :doc:`vfio_user`
- :ref:`GPU 地址翻译 <sim-gem5-address-translation>`
- :ref:`vHost 配置 <topo-vhosts>`
- :ref:`产物、路径与源码地图 <ref-files-and-artifacts>`

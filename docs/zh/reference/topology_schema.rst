.. SPDX-License-Identifier: Apache-2.0

.. _ref-topology-schema:

拓扑 YAML schema
================

本页是拓扑字段的可读参考。``cosim schema`` 输出机器可读的 JSON Schema。
未知字段会直接报错。

核心结构
--------

拓扑包含可复用的 ``kinds``、``templates``，以及一台或多台 ``machines``。
一台机器只有两个结构部分：

.. code-block:: yaml

   machines:
     - id: m0
       vhost: {use: vhost-x86-rocm}
       devices: [{use: mi300x}]

``vhost`` 描述 QEMU 虚拟主机以及其操作系统如何启动；``devices`` 描述独立运行的
设备模型。机器内容没有第三层概念。

文档字段
--------

.. list-table::
   :header-rows: 1

   * - 字段
     - 含义
   * - ``version``
     - 必填整数；当前为 ``1``。
   * - ``imports``
     - YAML 文件；先相对导入文件解析，再从 ``--resources`` 目录解析。
   * - ``templates``
     - 可复用的机器、vHost 或设备映射。映射递归合并，序列整体替换。
   * - ``kinds``
     - 适配器类型。``role`` 为 ``vhost`` 或 ``device``，并提供 ``argv`` 或 ``command``。
   * - ``machines``
     - 一项或多项机器声明；``count`` 可以展开声明。

机器字段
--------

``id`` 必填，并忽略 ASCII 大小写保持唯一。``use`` 选择模板，``count`` 默认为一，
``vhost`` 必填，``devices`` 默认为空列表；``placement.agent`` 为分布式执行预留。

vHost 字段
----------

基础执行字段包括 ``kind``、``runtime``、``memory``、``memory_align``、
``memory_map``、``cpus``、``accel``、``machine``、``cpu``、``display``、
``monitor``、``no_reboot``、``serial`` 和 ``args``。仓库自带的 vHost kind 使用 QEMU。

同一个 ``vhost`` 映射也直接拥有操作系统输入：

.. list-table::
   :header-rows: 1

   * - 字段
     - 类型/默认值
     - 含义
   * - ``image``
     - 可选配方标识
     - 相对 ``resources/images/recipes`` 的五层路径。
   * - ``kernel``
     - 可选路径
     - 未选择镜像配方时用于直接启动的内核。
   * - ``initrd``
     - 可选路径
     - 初始内存盘；要求同时声明 ``kernel``。
   * - ``cmdline``
     - 可选字符串
     - 内核命令行；要求声明 ``image`` 或 ``kernel``。
   * - ``root_bus``
     - 磁盘总线，默认 ``virtio``
     - ``image`` 产出的根磁盘使用的总线。
   * - ``disks``
     - 列表，默认 ``[]``
     - 挂载到该 vHost 的附加磁盘。
   * - ``snapshot``
     - 布尔值，默认 ``false``
     - 通过每会话 overlay 打开可写的显式磁盘；明确声明的只读磁盘仍保持只读。

``image`` 不能与 ``kernel`` 或 ``initrd`` 同时使用。运行时，其已验证磁盘会作为
``root`` 磁盘加入，导出的内核用于直接启动。因此选择 ``image`` 时，显式磁盘不能
再使用 ``root`` 标识或设置 ``boot: true``。

磁盘字段
--------

每块磁盘需要唯一的 ``id``，并且必须且只能声明 ``path`` 或 ``backing`` 之一。
``format`` 为 ``raw`` 或 ``qcow2``，默认 ``qcow2``；``bus`` 为 ``virtio``、
``nvme``、``ide`` 或 ``scsi``，默认 ``virtio``。``boot`` 最多标记一块启动盘。
``create`` 要求同时提供 ``path`` 与 ``size``。``shared: true`` 要求
``readonly: true``；直接写入要求两者都为 false。

设备字段
--------

设备可以使用 ``id``、``use``、``kind``、``count``、``config``、``ready_log``、
``runtime``、``memory_regions``、``pci``、``args`` 和 ``guest_hints``。适配器特有
要求见 :doc:`device_adapters`。使用 ``guest_hints.cmdline`` 时，其所属 vHost 必须
选择 ``image`` 或 ``kernel``。

路径与限制
----------

资源路径相对工作区根目录解析；相对路径不能包含 ``..``。标识由 1 到 48 个 ASCII
字母、数字、下划线或连字符组成。拓扑最多包含 4096 台机器，每台机器最多 256 个
设备；vHost kind 可以通过 ``max_devices`` 设置更小的限制。

验证修改：

.. code-block:: bash

   just run-cli schema
   just run-cli validate resources/machines/single-gpu.yaml --assets
   just check-cosim

镜像配方字段见 :ref:`ref-vhost-image-recipe`。

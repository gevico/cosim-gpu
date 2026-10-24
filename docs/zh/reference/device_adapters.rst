.. SPDX-License-Identifier: Apache-2.0

.. _ref-device-adapters:

设备适配器
==========

本页是设备与 host 适配器启动契约的唯一事实源：适配器种类、``kind``、参数、渲染出的 ``argv`` 与就绪探测顺序都在这里定义。模型的硬件行为见第 4 章，本页只讲启动接口。

适配器清单
----------

仓库内置两类设备适配器，另有一个模板适配器用于声明自定义设备；host 侧只有一个 ``qemu-vhost`` 适配器。

.. list-table::
   :header-rows: 1

   * - 适配器
     - kind
     - 模型
     - 启动程序
     - 就绪探测
     - 说明
   * - ``gem5-mi300x``
     - built-in
     - gem5
     - ``gem5.opt`` + ``mi300_cosim.py``
     - 日志标记，然后 vfio-user socket
     - 一个进程一个 GPU
   * - ``qemu-device``
     - built-in
     - QEMU
     - ``qemu-system-<arch>``
     - 可选日志标记，然后 socket，再 QMP
     - ``x-remote`` 与 ``x-vfio-user-server`` 导出一个 PCI 设备
   * - 模板设备
     - ``kinds`` 中声明，``role: device``
     - ``gem5`` 或 ``qemu``
     - ``argv`` 或 ``command``
     - 日志标记，然后 socket
     - ``runtime.argv`` 或 ``runtime.command`` 可覆盖任何设备的命令

gem5-mi300x
-----------

``gem5-mi300x`` 为每个进程启动一个 gem5 MI300X GPU；YAML 路径固定 ``--num-gpus=1``，多 GPU 由多个设备进程实现。

.. list-table::
   :header-rows: 1

   * - 字段
     - 必填
     - 默认值
     - 说明
   * - ``config``
     - 是
     - —
     - 指向 ``third_party/gem5/configs/example/gpufs/mi300_cosim.py``
   * - ``runtime.binary``
     - 否
     - ``gem5.opt``
     - 相对工作区根目录，或不含 ``/`` 时从 ``PATH`` 查找
   * - ``memory_regions``
     - 是
     - —
     - 恰好一个名为 ``vram`` 的区域，大小为 2 的幂，对齐不小于一页
   * - ``pci``
     - 否
     - —
     - 提供时必须等于 ``0x1002`` 与 ``0x74a0``、256 个 MSI-X 向量
   * - ``args.num_compute_units``
     - 否
     - ``40``
     - 取值 1 到 1024
   * - ``args.gem5_debug_flags``
     - 否
     - ``[]``
     - 写入 ``--debug-flags`` 的 gem5 调试标志列表
   * - ``args.extra``
     - 否
     - ``[]``
     - 追加到 ``mi300_cosim.py`` 命令行末尾的参数
   * - ``ready_log``
     - 否
     - 默认监听行
     - 覆盖就绪探测使用的日志标记
   * - ``guest_hints.modprobe``
     - 否
     - —
     - 写入执行计划，launcher 不执行

渲染出的命令：

.. code-block:: bash

   gem5.opt --outdir=<node>/m5out [--debug-flags=<csv>] --listener-mode=off \
            <config> --socket-path=<device.sock> --shared-pool=<pool> \
            --pool-vram-offset=<offset> --dgpu-mem-size=<size>B \
            --mem-size=<ram>B --host-memory-ranges=<json> \
            --num-compute-units=<n> --num-gpus=1 [extra...]

就绪探测按顺序执行：先等日志出现默认标记 ``MI300XVfioUser: listening on <socket> (vfio-user protocol)`` （或 ``ready_log`` 覆盖值），再确认 socket 存在。机器含 ``gem5-mi300x`` 设备时 host 必须声明 ``memory_map``。

qemu-device
-----------

``qemu-device`` 用 ``-machine x-remote,vfio-user=on,auto-shutdown=off`` 启动 QEMU，并通过 ``x-vfio-user-server`` 对象导出一个 PCI 设备。样例只有 ``edu``。

.. list-table::
   :header-rows: 1

   * - 字段
     - 必填
     - 默认值
     - 说明
   * - ``runtime.binary``
     - 是
     - —
     - 必须是用 ``--enable-vfio-user-server`` 构建的 QEMU，``just build-qemu`` 产出 ``build/qemu/qemu-system-<arch>``
   * - ``args.device``
     - 是
     - —
     - QEMU ``-device`` 属性映射，必须包含非空 ``driver``；``id`` 缺省为 ``device0``，且必须是合法标识符
   * - ``args.extra``
     - 否
     - ``[]``
     - 追加到 QEMU 命令行末尾的参数
   * - ``config``
     - 否
     - —
     - 拒绝该字段；设备参数全部放在 ``args.device``
   * - ``memory_regions``
     - 否
     - —
     - 拒绝私有内存区域；需要私有内存时改用运行时命令模板
   * - ``ready_log``
     - 否
     - 无
     - 可选的日志标记；设置后会追加为第一个探测

渲染出的命令：

.. code-block:: bash

   <qemu-system-<arch>> -machine x-remote,vfio-user=on,auto-shutdown=off -nodefaults \
     -display none -qmp unix:<qmp>,server=on,wait=off \
     -device '<args.device JSON>' \
     -object '{"qom-type":"x-vfio-user-server","id":"vfio0","socket":{"type":"unix","path":"<socket>"},"device":"<device.id>"}'

就绪探测按顺序执行：可选的日志标记，socket 存在，QMP 协商成功。该设备需要带 ``--enable-vfio-user-server`` 的 QEMU 构建。

模板设备与自定义命令
--------------------

在 ``kinds`` 中声明 ``role: device`` 并提供 ``argv`` 或 ``command`` 即可接入自定义模型；两者互斥，且设备必须声明 ``ready_log``。``runtime.argv`` 或 ``runtime.command`` 可以覆盖任何设备的启动命令，此时同样要求 ``ready_log``。

模板设备可用的上下文变量：

.. list-table::
   :header-rows: 1

   * - 变量
     - 含义
   * - ``id``
     - 设备标识符
   * - ``machine``
     - 所属机器标识符
   * - ``socket``
     - 设备提供给 host 的 vfio-user socket 路径
   * - ``pool``
     - 整台机器的内存池文件路径
   * - ``ram``
     - 客户机内存区域（``offset``、``size``、``align``）
   * - ``regions``
     - 该设备的私有区域，按名称索引
   * - ``guest_ranges``
     - 客户机物理地址区间，用于 ``--host-memory-ranges``
   * - ``args``
     - 设备 ``args`` 映射
   * - ``config``
     - 设备 ``config`` 路径
   * - ``model``
     - 设备模型，``gem5`` 或 ``qemu``
   * - ``run_dir``
     - 会话运行目录
   * - ``node_dir``
     - 该设备节点的工作目录

渲染结果必须是非空参数数组；未定义变量会报错。探测顺序为日志标记，然后 socket。

vHost 适配器契约
-----------------

vHost kind 必须声明 ``role: vhost``、``model: qemu``，并提供 ``argv`` 或 ``command``；``max_devices`` 只对 vHost kind 生效（``qemu-vhost`` 为 64）。``qemu-vhost`` 的命令模板先为每个设备分配 PCIe root port，再挂载磁盘，最后追加 ``vhost.args``。

vHost 模板可用的上下文变量：

.. list-table::
   :header-rows: 1

   * - 变量
     - 含义
   * - ``vhost``
     - 校验后的 vHost 对象，含 ``machine``、``accel``、``cpus``、``args`` 等字段
   * - ``machine``
     - 机器标识符
   * - ``pool``
     - 内存池文件路径
   * - ``ram``
     - 客户机内存区域
   * - ``guest_ranges``
     - 客户机物理地址区间
   * - ``boot``
     - vHost 的直连启动配置，可为空
   * - ``disks``
     - 渲染后的磁盘列表，含 ``path``、``format``、``readonly``、``bus``、``boot``
   * - ``devices``
     - 设备端点列表，含 ``id``、``socket``、``model``、``pci``
   * - ``qmp`` / ``serial`` / ``serial_log``
     - QMP socket、串口 socket 与串口日志路径
   * - ``cmdline``
     - vHost 的 ``cmdline`` 与所有设备 ``guest_hints.cmdline`` 空格连接的结果
   * - ``run_dir`` / ``node_dir``
     - 会话运行目录与该 vHost 节点的工作目录

vHost 程序必须在前台运行、把资源使用者保留在自己的进程组中并保持继承的文件描述符打开；QEMU 的 ``-daemonize`` 会被拒绝。

就绪探测与超时
--------------

每个进程启动后按顺序执行探测，全部通过即视为就绪；每项探测必须在 ``--ready-timeout`` （默认 120 秒）内成功。``serial.timeout`` 为串口标记单独指定 1 到 86400 秒的期限。设备先于 vHost 就绪，vHost 先于设备停止。

.. list-table::
   :header-rows: 1

   * - 探测
     - 通过条件
     - 使用方
   * - ``Log``
     - 进程标准输出日志包含指定标记
     - 设备自定义命令；vHost 的可选 ``serial.wait_for``
   * - ``Socket``
     - Unix socket 路径存在
     - gem5 设备、模板设备、vHost 串口 socket
   * - ``Qmp``
     - QMP 服务器完成 capabilities 协商
     - ``qemu-device`` 设备与 host

来源与维护
----------

契约定义与适配器实现：

- ``crates/cosim-topology/src/adapter/mod.rs``：``Adapter``、``Launch``、``Probe``、模板上下文。

- ``crates/cosim-topology/src/adapter/gem5.rs``：``gem5-mi300x`` 参数与 argv。

- ``crates/cosim-topology/src/adapter/qemu_device.rs``：``qemu-device`` 参数与 argv。

- ``crates/cosim-topology/src/adapter/template.rs``：模板设备与命令渲染。

- ``resources/devices/``：设备模板样例；``resources/vhosts/qemu.yaml``：host 命令模板。

修改后运行：

.. code-block:: bash

   just run-topology resources/machines/qemu-device.yaml --dry-run
   just run-cli validate resources/machines/single-gpu.yaml  --assets
   just check-cosim

相关页面
--------

- 设备字段与 vHost：:doc:`topology_schema`

- 客户机驱动参数：:doc:`guest_parameters`

- 设备目录：:ref:`topo-devices`

- QEMU device model 与 gem5 MI300X 模型：:ref:`sim-qemu-device-models`、:ref:`sim-gem5-model`

- MI300X PCI/BAR 接口：:ref:`sim-gem5-pci`

- Rust 工作区与扩展点：:ref:`launcher-rust-workspace`

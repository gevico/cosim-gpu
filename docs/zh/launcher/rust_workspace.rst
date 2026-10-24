.. SPDX-License-Identifier: Apache-2.0

.. _launcher-rust-workspace:

Rust 工作区
============

本页说明启动器的 crate 划分、模块职责、公开接口和扩展点，供修改启动器或接入新设备模型时参考。

工作区结构
-----------

工作区包含 ``cosim-topology``\ 、``cosim-runtime``\ 和 ``cosim-cli``\ 三个 crate。``cosim-cli``\ 依赖另外两个 crate，``cosim-runtime``\ 依赖 ``cosim-topology``\ ，依赖方向决定了“文档解析不接触主机，执行逻辑才接触主机”的分层。

.. mermaid::

   flowchart TD
       C[cosim-cli] --> T[cosim-topology]
       C --> R[cosim-runtime]
       R --> T

模块职责
---------

.. list-table::
   :header-rows: 1

   * - 路径
     - 职责
   * - ``crates/cosim-cli/src/main.rs``
     - Clap 子命令、信号升级、标准输入生命线、事件输出和 verdict 行。
   * - ``crates/cosim-topology/src/raw.rs``\ 、``model.rs``\ 、``size.rs``
     - 解码后的输入类型、校验后的类型（``Topology``\ 、``Machine``\ 、``Vhost``\ 、``Device``\ 、``Disk``\ ）和 ``ByteSize``\ 。
   * - ``crates/cosim-topology/src/loader.rs``\ 、``resolve.rs``
     - 导入、合并键、模板继承、工作区相对资源路径、数量展开和校验。
   * - ``crates/cosim-topology/src/adapter/``
     - ``Adapter``\ 枚举及 ``gem5-mi300x``\ 、``qemu-device``\ 和模板适配器，host 参数渲染和 ``Probe``\ 。
   * - ``crates/cosim-topology/src/layout.rs``
     - 给定 ``PageSize``\ 时计算内存池和客户机物理地址区间。
   * - ``crates/cosim-runtime/src/env.rs``\ 、``layout.rs``\ 、``plan.rs``
     - ``ExecEnv``\ 、``SessionLayout``\ 和可序列化的 ``Plan``\ 。
   * - ``crates/cosim-runtime/src/session.rs``\ 、``node.rs``\ 、``probe.rs``
     - 会话资源、节点类型状态、依赖租约、就绪探测和 verdict。
   * - ``crates/cosim-runtime/src/process.rs``\ 、``resource.rs``\ 、``disk.rs``\ 、``manifest.rs``
     - 进程组、文件和锁的所有者、镜像创建与 overlay、异常退出后的 ``clean``\ 。

公开接口
---------

- ``cosim-topology``\ 公开 ``load``\ 、``graph``\ 和 ``schema``\ ；校验后的类型根据 ``DeviceContext``\ 和 ``VhostContext``\ 渲染启动参数。
- ``cosim-runtime``\ 公开 ``plan``\ 、``run``\ 、``clean``\ 、``check_assets``\ 、``RunOptions``\ 、``Shutdown``\ 和 ``Event``\ 。
- ``Plan``\ 记录程序、参数、环境、依赖、就绪探测、共享内存区域、磁盘目标和锁文件路径，``cosim run --dry-run``\ 打印的就是它。

扩展点：适配器与命令模板
-------------------------

- 设备适配器由 ``Adapter``\ 枚举表达：``gem5-mi300x``\ 运行一个进程内一个 GPU，``qemu-device``\ 导出 QEMU 功能设备，模板适配器按 YAML 渲染命令。
- 就绪条件由 ``Probe``\ 表达：日志标记、Unix socket 存在和 QMP 协商；适配器按顺序返回这些探测。
- vHost kind 通过 YAML ``command``\ 模板渲染 QEMU 参数；``kinds``\ 中 ``role: device``\ 的 kind 提供 ``argv``\ 或 ``command``\ ，并需要 ``ready_log``\ 。
- ``runtime.argv``\ 或 ``runtime.command``\ 可以替换任何设备适配器生成的命令，但必须自己保证就绪探测和资源约定。
- ``gem5-mi300x``\ 要求 ``config``\ 、恰好一个大小为 2 的幂的 ``vram``\ 区域，以及匹配 MI300X 的 PCI 元数据；``num_compute_units``\ 的范围是 1 到 1024，默认 40。
- ``qemu-device``\ 要求 ``args.device.driver``\ ，``id``\ 默认为 ``device0``\ ，不接受私有内存区域，并需要 ``runtime.binary``\ 。

接入新模型的步骤
-----------------

1. 在 ``resources/devices/``\ 中添加模板，声明 ``kind``\ 、``config``\ 或 ``runtime``\ 、内存区域和 PCI 元数据。
2. 选择内置适配器，或在 ``kinds``\ 中声明 ``role: device``\ 的模板 kind 并提供命令与 ``ready_log``\ 。
3. 在 ``resources/machines/``\ 中添加引用该模板的机器样例，并运行 ``cosim validate``\ 与 ``cosim run --dry-run``\ 检查渲染结果。
4. 如果模型需要新的就绪方式或参数语义，修改 ``crates/cosim-topology/src/adapter/``\ 并补充 Rust 测试。

依赖与安全规则
---------------

- YAML 语法与合并键由 ``serde_yaml_ng``\ 处理，Serde 负责类型反序列化。
- MiniJinja 渲染参数模板，Schemars 生成 JSON Schema，``parse-size``\ 解析大小表达式。
- Tokio 在单个线程上运行会话，``futures-util``\ 并发推进各进程节点，``nix``\ 提供进程组信号、页大小和文件系统统计接口。
- 项目的 Rust crate 从工作区继承 ``unsafe_code = "forbid"``\ ；设备模型通过适配器边界接入，不在启动器内直接操作模型内部状态。
- 检查命令：``just check-cosim``\ 运行格式、clippy 和单元测试，``just test-cosim-integration``\ 运行真实进程与磁盘的集成测试。

源码与依据
-----------

- 三个 crate 的清单与依赖：``crates/cosim-cli/Cargo.toml``\ 、``crates/cosim-runtime/Cargo.toml``\ 、``crates/cosim-topology/Cargo.toml``\ 。
- 适配器实现：``crates/cosim-topology/src/adapter/gem5.rs``\ 、``qemu_device.rs``\ 、``template.rs``\ 。
- 运行库导出：``crates/cosim-runtime/src/lib.rs``\ 。
- Rust 规范：``docs/zh/contributing/rust_guidelines.rst``\ 。

相关页面
---------

- :doc:`yaml_pipeline`\ ：适配器在计划生成阶段的作用。
- :ref:`ref-device-adapters`\ ：设备适配器契约的唯一事实源。
- :ref:`arch-components`\ ：组件与职责的系统视图。
- :ref:`contrib-rust-guidelines`\ ：Rust 代码与提交规范。

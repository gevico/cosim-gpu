.. SPDX-License-Identifier: Apache-2.0

.. _ref-simulator-device-recipes:

模拟器与设备配方
================

模拟器配方负责工具构建和通用执行入口；设备配方负责模型选择、参数和启动契约；
machine 负责设备实例及连接。vHost 镜像仍见 :ref:`ref-vhost-image-recipe`。

目录与职责
----------

.. code-block:: text

   resources/
     images/recipes/ubuntu/24.04/x86_64/rocm/7.0/
     vhosts/qemu.yaml
     device_simulators/
       builder.py
       recipe.py
       cli.py
       gem5/
         recipe.toml
         run.py
     devices/gpu/mi300x/
       device.toml
       gem5.yaml
       gem5.py
     machines/single-gpu.yaml

``vhosts/qemu.yaml`` 管理 QEMU vHost 的启动契约，``gem5.yaml`` 管理 MI300X 的
gem5 启动契约。QEMU 设备模型的设备参数也应留在对应设备配置中，不归 vHost 配置。
模拟器标识只命名工具（``gem5``）；设备配方标识为
``类别/型号/后端`` （``gpu/mi300x/gem5``）。

模拟器配方
----------

``device_simulators/gem5/recipe.toml`` 使用 ``schema = 1``，字段均为必填：

.. list-table::
   :header-rows: 1

   * - 字段
     - 含义
   * - ``source.path``
     - 工作区源码路径 ``third_party/gem5``，版本由 gitlink 固定。
   * - ``build.config``
     - gem5 能力构建配置 ``VEGA_X86``。
   * - ``build.binary``
     - 输出文件名 ``gem5.opt``。
   * - ``runtime.entry``
     - 模拟器目录内的入口文件名 ``run.py``。

构建产物为 ``build/gem5/<host-architecture>/VEGA_X86/``。
``GEM5_BUILD_DIR`` 可指定工作区 ``build/`` 内的其他目录。
``VEGA_X86`` 是 gem5 的构建配置，与 QEMU 客户机 ISA、编译可执行文件的 Host 架构分开。

``run.py --model-config <设备 YAML>`` 加载配方和指定的 Python 模型。
模型提供 ``add_arguments(parser, recipe)`` 和 ``build(args)``，后者返回 gem5
``Root``。通用入口负责 ``m5.instantiate`` 和事件循环。MI300X 模型负责 GPU、
Ruby/TLB、桥接对象及最小 gem5 System 支撑对象；客户机 CPU 和操作系统由 QEMU 运行。

设备配方
--------

``device.toml`` 使用 ``schema = 1``，其 ``pci`` 表统一管理 PCI 身份和 ROM 路径。
``gem5.yaml`` 使用拓扑文档的 ``version: 1``，同时包含 ``recipe`` 和原有的
``templates`` 别名：

.. list-table::
   :header-rows: 1

   * - 配方字段
     - 含义
   * - ``simulator``
     - 工具配方引用 ``gem5``。
   * - ``kind``
     - 设备启动契约 ``gem5-mi300x``。
   * - ``model``
     - 设备目录内的 Python 组装模块 ``gem5.py``。
   * - ``ready_log``
     - 就绪日志标记模板。
   * - ``runtime.command``
     - 生成 JSON 参数数组的 MiniJinja 模板，见 :ref:`ref-device-adapters`。
   * - ``defaults``
     - 设备默认值，包括 VRAM、MSI-X 向量数及客户机驱动提示。
   * - ``parameters``
     - 暴露参数的默认值和约束。``integer`` 包含 ``default``、``min``、``max``；
       ``string-list`` 包含字符串数组 ``default``。未知参数名会报错。
   * - ``requirements``
     - ``memory_map`` 要求提供 vHost 地址映射；``regions`` 声明必需内存区域及
       ``power_of_two`` 约束。

组装顺序是设备身份、后端默认值、machine 实例覆盖值，最终结果必须满足配方约束。
实例不能替换 PCI 身份、入口或选定的模型配置。配方路径禁止父目录穿越和逃出
所选库或模型目录的符号链接。命令模板收到的 ``entry`` 是模拟器入口，``config``
是设备 YAML。暴露的 CU 和 VRAM 默认值也用于模型直接 CLI 的默认参数。

选择与构建
----------

.. code-block:: yaml

   devices:
     - id: gpu0
       recipe: gpu/mi300x/gem5
       host_arch: x86_64
       memory_regions: [{name: vram, size: 8G}]
       args: {num_compute_units: 4}

``host_arch`` 选择 ``x86_64`` 或 ``aarch64`` 的原生可执行文件，默认取 launcher
所在 Host 架构。``runtime.binary`` 允许显式覆盖二进制路径。
``use: mi300x`` 和 ``use: mi300x-aarch64`` 仍由 ``gem5.yaml`` 提供。
当前 machine 配方每张 GPU 启动一个进程。MI300X 组装模块的直接 CLI 可在一个进程内
构造多张 GPU，但 shared-pool 模式当前要求一张 GPU。本次拆分不引入跨模拟器设备互联
或新的进程分组机制。

.. code-block:: bash

   just run-simulator-recipe
   just dev-image
   just build-gem5
   just test-simulator-recipes
   just check-cosim

``builder.py`` 通过 ``just build-gem5`` 运行 SCons，``COSIM_ENV`` 选择原生执行或
共用开发容器。legacy launcher 在 ``cosim-dev`` 中运行挂载的二进制、源码配置库和
设备配置，不再单独封装 gem5 运行镜像。Rust launcher 可原生执行，也可整体运行于
该开发容器。调整模型配置不需要重新编译 gem5。CI 传递一个开发镜像并校验其精确身份、
二进制和校验和；构建缓存键不包含运行时模型文件。

相关页面
--------

- vHost 镜像：:doc:`vhost_image_recipe`
- 启动契约：:doc:`device_adapters`
- 拓扑字段：:doc:`topology_schema`
- 设备目录：:ref:`topo-devices`

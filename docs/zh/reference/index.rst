.. SPDX-License-Identifier: Apache-2.0

.. _ref-index:

参考手册
========

本章是 schema、参数、版本、文件路径、GART 格式与已知问题的唯一事实源：
其他章节只解释行为，表格统一链接到这里，避免同一份数据在多个页面维护。

.. toctree::
   :maxdepth: 1

   topology_schema
   device_adapters
   vhost_image_recipe
   guest_parameters
   version_matrix
   files_and_artifacts
   gart_format
   known_issues
   legacy_launcher_flags

推荐阅读路径
------------

- 第一次启动客户机、驱动没有加载：先看 :doc:`guest_parameters`，再按症状在
  :doc:`known_issues` 中查找。
- 编写或修改拓扑 YAML：从 :doc:`topology_schema` 查字段与默认值，设备启动约定见
  :doc:`device_adapters`，完整写法见 :ref:`topo-write-topology`。
- 复现构建或排查版本差异：先查 :doc:`version_matrix`，再按
  :doc:`files_and_artifacts` 定位产物、日志与源码。
- 新增或审查 vHost 镜像 recipe：字段与产物规则见
  :doc:`vhost_image_recipe`，贡献步骤见 :ref:`contrib-add-vhost-recipe`。
- 排查 GPU 地址翻译与 GART 表：:doc:`gart_format` 给出表项与寄存器格式，翻译流程见
  :ref:`sim-gem5-address-translation`。
- 维护或对照遗留 shell launcher：:doc:`legacy_launcher_flags` 是该路径的唯一参数表。

事实源约定
----------

.. list-table::
   :header-rows: 1

   * - 页面
     - 拥有的内容
     - 主要来源
   * - :doc:`topology_schema`
     - 拓扑与 vHost 的字段、类型、默认值与上限
     - ``crates/cosim-topology/src/raw.rs``、``resolve.rs``
   * - :doc:`device_adapters`
     - 各设备适配器的参数、argv 与就绪探测
     - ``crates/cosim-topology/src/adapter/``
   * - :doc:`vhost_image_recipe`
     - vHost 镜像 recipe 的目录、字段、输入身份与 bundle 格式
     - ``resources/images/recipe.py``、``identity.py``、``bundle.py``
   * - :doc:`guest_parameters`
     - amdgpu 模块参数、ROM 写入、内核命令行、IP block mask
     - ``tests/test_modprobe_params.sh``、镜像 recipe
   * - :doc:`version_matrix`
     - 记录版本、镜像 tag 与 provenance
     - ``third_party/qemu/VERSION``、``recipe.toml``、``Cargo.toml``
   * - :doc:`files_and_artifacts`
     - 源码目录、构建产物、会话目录、客户机文件与环境变量
     - 仓库目录结构、``crates/cosim-runtime/src/layout.rs``
   * - :doc:`gart_format`
     - GART PTE、aperture 寄存器与典型布局
     - ``third_party/gem5/src/dev/amdgpu/amdgpu_vm.cc``
   * - :doc:`known_issues`
     - 按 symptom/cause/fix 组织的问题目录
     - 历史问题记录与驱动、模型行为
   * - :doc:`legacy_launcher_flags`
     - shell launcher 与 gem5 config 的修正参数表
     - ``scripts/host/cosim_launch.sh``、``mi300_cosim.py``

相关章节
--------

- 拓扑字段的使用方式：:ref:`topo-write-topology`
- vfio-user 接口与设备模型：:ref:`sim-qemu-device-models`、:ref:`sim-gem5-pci`
- 客户机驱动要求：:ref:`sim-guest-driver`
- 命令与会话生命周期：:ref:`launcher-cli`、:ref:`launcher-session-lifecycle`

.. SPDX-License-Identifier: Apache-2.0

.. _contrib-index:

贡献指南
========

本页是贡献流程的入口。提交补丁之前先阅读本章，并按页面末尾的检查清单确认提交内容。

本章内容
--------

.. toctree::
   :maxdepth: 1

   workflow
   add_vhost_recipe
   patch_check
   maintainers
   ci
   rust_guidelines
   documentation

推荐路径
--------

- 第一次提交：先读 :doc:`workflow`，再读 :doc:`patch_check`
- 新增客户机发行版或镜像变体：阅读 :doc:`add_vhost_recipe`
- 修改 Rust 代码：补充阅读 :doc:`rust_guidelines`
- 修改文档页面：阅读 :doc:`documentation`，并运行 ``just docs-check``
- 需要知道由谁审查：查看 :doc:`maintainers`

提交前检查
----------

- 每个非合并提交都通过 ``just check-patch``
- 提交带有 ``Signed-off-by:`` 行，且不包含 AI 归属尾注
- 新增文件属于 ``MAINTAINERS.yml`` 中已有的 area，或在同一提交中补充
- 同时修改中英文页面时，两种语言在同一提交中更新

相关页面
--------

- :doc:`workflow`
- :doc:`patch_check`
- :doc:`documentation`
- :ref:`gs-index`

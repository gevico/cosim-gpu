.. SPDX-License-Identifier: Apache-2.0

.. _contrib-workflow:

开发与提交流程
==============

本页说明从准备环境到提交补丁的流程。补丁的格式要求见 :doc:`patch_check`，
文件归属见 :doc:`maintainers`。

环境与前置条件
--------------

构建、启动、测试与检查任务都定义在仓库根目录的 ``justfile`` 中。在仓库根目录
运行 ``just`` 可以列出全部任务，任务按 ``dev-``、``build-``、
``run-``、``test-``、``check-``、``ci-`` 和 ``maint-``
前缀分组。

QEMU、gem5、Rust 与拓扑相关任务在 Linux 主机上原生运行；其他系统，或设置了
``COSIM_ENV=container`` 的 Linux 主机，默认在临时开发容器中运行。环境要求与
工具版本见 :ref:`gs-requirements`，容器用法见 :ref:`gs-platform-container`。

子模块与仓库边界
----------------

``gem5``、``qemu`` 和 ``gem5-resources`` 是子模块。子模块内的修改
遵守对应仓库自己的规则，顶层仓库的检查规则只适用于本仓库的文件。

- 初始化与更新子模块使用 ``git submodule update --init --recursive``。
- 更新子模块指针与修改顶层文件分开提交，便于审查和回滚。
- 子模块改动需要先在子模块仓库中完成审查，再更新顶层指针。

分支与提交
----------

- 从 ``main`` 创建分支，一个分支专注一件事。
- 保持提交聚焦，每个非合并提交都必须能独立通过补丁检查。
- 提交信息使用祈使句描述改动，正文说明原因与影响。
- 每个提交都必须带有 ``Signed-off-by:`` 行，格式为
  ``Signed-off-by: Name <email>``，姓名与邮箱取自
  ``git config user.name`` 和 ``git config user.email``。
- 提交信息中不添加 AI 归属尾注，例如面向 AI 工具的 ``Co-authored-by:``、
  ``Assisted-by:``、``Generated-by:`` 或 ``🤖`` 标记。
- 新增源文件以 ``SPDX-License-Identifier:`` 行开头，项目许可证为
  ``Apache-2.0``；来自 ``MIT``、``BSD-2-Clause`` 或
  ``BSD-3-Clause`` 源码的代码可以使用对应许可证，并在提交信息中说明原因。

提交前检查
----------

在提交或更新拉取请求之前运行：

.. code-block:: bash

   just check

该任务依次运行 ``just check-patch``、ShellCheck、``just check-maintainers``
和 ``just check-cosim``。也可以单独运行其中一项：

.. code-block:: bash

   just check-patch                     # 当前分支上尚未进入 origin/main 的提交
   just check-patch <base-commit>       # 指定基线之后的提交
   just check-patch-file <patch>        # 预览未提交的补丁文件

修改文档时额外运行 ``just docs-check``，它会构建中英文文档并执行双语与站点
检查；文档规则见 :doc:`documentation`。

文件归属
--------

每个受版本控制的文件都必须属于 ``MAINTAINERS.yml`` 中的一个 area。提交在现有
area 之外新增文件时，必须在同一个提交中更新 ``MAINTAINERS.yml``，否则
``just check-maintainers`` 会失败。area 的查询、检查与新增维护者见
:doc:`maintainers`。

相关页面
--------

- :doc:`patch_check`
- :doc:`maintainers`
- :doc:`documentation`
- :ref:`gs-requirements`
- :ref:`ref-version-matrix`

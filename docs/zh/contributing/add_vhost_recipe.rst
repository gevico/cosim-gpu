.. SPDX-License-Identifier: Apache-2.0

.. _contrib-add-vhost-recipe:

新增 vHost 镜像配方
===================

当新的发行版、架构或软件版本需要不同的镜像构建过程时，使用本流程。只有运行时
参数不同，应修改 vHost 模板，而不是增加镜像配方。

1. 选择标识
-----------

严格创建五层目录::

   resources/images/recipes/
     <发行版>/<发行版版本>/<架构>/<软件>/<软件版本>/

路径就是标识。不要再增加第二个标识，也不要在 ``recipe.toml`` 中重复路径信息。

2. 声明构建
-----------

添加 ``recipe.toml``，按 :ref:`ref-vhost-recipe-toml` 填写基础镜像、安装参数和
导出文件。固定基础镜像的 SHA-256，并确认所选 CPU、内存、磁盘容量和加速方式
能满足本次镜像构建。

配方自己的脚本、服务和配置放入 ``files/``，在 ``provision.yml`` 中通过
``{{ playbook_dir }}/files`` 引用。默认只使用一个 playbook；在没有实际复用需求时，
不要再引入第二个 task 入口文件。

3. 安装镜像内容
---------------

参照 :ref:`ref-vhost-recipe-provision` 编写 ``provision.yml``，安装 vHost 所需的
系统包、内核、驱动和服务。读取配方传入的变量，并用末尾的 ``fetch`` 步骤取回
声明的导出文件。

需要开机初始化时，将 ``initialize`` 脚本和对应的 systemd 服务安装进镜像，
并启用该服务。镜像构建时完成软件安装，以后启动的 vHost 再执行开机初始化。

不要把全系统 gem5 支持或模拟器专用控制工具加入镜像。本项目由 QEMU 运行操作
系统，并单独连接 Device Model。

4. 连接 vHost 样例
------------------

在 ``resources/vhosts/`` 下新增或修改模板：

.. code-block:: yaml

   templates:
     vhost-example:
       use: vhost-x86
       image: <发行版>/<发行版版本>/<架构>/<软件>/<软件版本>
       cmdline: console=ttyS0 root=/dev/vda1 rw
       root_bus: virtio

机器样例在 ``machine.vhost`` 下选择该 vHost；镜像与启动字段仍属于同一份拓扑。

5. 验证
-------

先运行不构建大镜像的检查：

.. code-block:: bash

   just ci-rocm-assets inspect <配方标识>
   just ci-rocm-assets validate <配方标识> --syntax-only
   just docs-check

``--syntax-only`` 检查 Packer 和 Ansible 的语法，不启动构建虚拟机；首次运行可能
下载所需工具。另用 :ref:`contrib-ci` 中的 Python 检查覆盖配方解析与镜像复用逻辑。

真实镜像构建只应在 Linux KVM 主机或镜像 CI 任务中运行。构建后检查 manifest，
并启动一个选择该 vHost 的机器。只有在实现过程中真实遇到发行版特有问题后，
才把经验补充到本指南。

相关页面
--------

- 配方字段与安装文件：:ref:`ref-vhost-image-recipe`
- CI 验证流程：:doc:`ci`
- 文档规范和本地预览：:doc:`documentation`

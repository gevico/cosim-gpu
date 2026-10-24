.. SPDX-License-Identifier: Apache-2.0

.. _ref-vhost-image-recipe:

vHost 镜像配方
==============

镜像配方用于构建一个已经安装好软件、可供 vHost 启动的操作系统磁盘镜像。
本页统一说明 ``recipe.toml`` 的字段、``provision.yml`` 的写法和二者之间传递的变量。

构建器先用 QEMU 启动基础镜像，通过 SSH 连接这台临时虚拟机，再运行 Ansible
安装软件。安装完成并关机后，它的磁盘就是镜像产物；按配方声明复制出来的内核、
软件清单等文件与磁盘一起保存。

``provision`` 中的 CPU、内存和加速方式用于这台临时构建虚拟机。
以后启动仿真时使用的 CPU、内存、启动参数和磁盘总线由拓扑中的 ``vhost`` 决定。

配方标识
--------

目录就是配方标识，也是平台与软件版本的唯一事实源::

   resources/images/recipes/
     <发行版>/<发行版版本>/<架构>/<软件>/<软件版本>/

例如 ``ubuntu/24.04/x86_64/rocm/7.0`` 表示带 ROCm 7.0 的 Ubuntu 24.04
x86_64 镜像。不要在 ``recipe.toml`` 中重复这五项信息。
解析器接受的架构名称为 ``x86_64``、``aarch64`` 和 ``riscv64``；实际构建还需要
对应的基础镜像、QEMU 和安装步骤。

配方中的文件
------------

``recipe.toml``
   声明基础镜像、构建入口、构建变量以及成功构建后导出的文件。

``provision.yml``
   Ansible 安装文件；playbook 是 Ansible 对一组安装、配置步骤的称呼。
   其路径由 ``provision.playbook`` 指定。

``files/``
   playbook 复制进镜像的脚本、服务和配置。

安装和开机初始化是两个阶段：``provision.yml`` 在构建镜像时安装软件，
也可以复制 ``initialize`` 脚本并启用 systemd 服务，让以后启动的 vHost 自动执行
初始化。当前 GPU 初始化顺序见 :ref:`ref-guest-parameters`。

.. _ref-vhost-recipe-toml:

recipe.toml 字段
----------------

``recipe.toml`` 的三个配置段分别是：``base`` 指定基础镜像；``provision`` 描述
如何准备构建虚拟机并执行安装；``result`` 声明需要导出的文件。

顶层的 ``schema`` 是必填整数，表示配方文件的格式版本，当前值为 ``2``。
当前主要用它明确拒绝旧格式：解析器只接受 ``2``，不自动迁移旧配方。
新增 vHost、发行版或软件版本，以及调整模板中的配置值，都不需要修改 ``schema``。
只有配方字段结构发生不兼容变化时，才需要考虑更新格式版本，并迁移受影响的配方。

``base``、``provision`` 和 ``result`` 三个表都必须存在；未知字段会报错。
下文中的必填字段没有隐式默认值。

基础镜像：base
~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 字段
     - 类型 / 必填
     - 含义与约束
   * - ``url``
     - 字符串 / 是
     - 下载基础磁盘镜像的 HTTPS 地址。基础系统需要能够通过 SSH 接受安装操作；
       当前共享构建模板使用 cloud-init 配置临时登录密钥。
   * - ``sha256``
     - 字符串 / 是
     - 基础镜像的 SHA-256，64 个小写十六进制字符，不带 ``sha256:`` 前缀。
   * - ``format``
     - 字符串 / 是
     - 基础磁盘格式：``raw`` 或 ``qcow2``。

构建和安装：provision
~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 字段
     - 类型 / 必填
     - 含义与约束
   * - ``image_name``
     - 字符串 / 是
     - Packer 构建阶段的虚拟机和磁盘文件名称；最终发布的磁盘统一命名为 ``disk``。
   * - ``disk_size``
     - 字符串 / 是
     - 构建磁盘容量，交给 Packer 解释，例如 ``"40000M"``。
   * - ``disk_format``
     - 字符串 / 是
     - 产出磁盘格式：``raw`` 或 ``qcow2``，可以与 ``base.format`` 不同。
   * - ``cpus``
     - 整数 / 是
     - 临时构建虚拟机的 vCPU 数量，至少为 ``1``。
   * - ``memory_mb``
     - 整数 / 是
     - 临时构建虚拟机的内存，单位 MiB，至少为 ``512``。
   * - ``ssh_username``
     - 字符串 / 是
     - Packer 和 Ansible 连接临时构建虚拟机时使用的用户。
   * - ``accelerator``
     - 字符串 / 是
     - QEMU 加速方式：``kvm``、``tcg`` 或 ``hvf``；构建主机必须具备所选方式的运行条件。
   * - ``machine_type``
     - 字符串 / 是
     - 构建虚拟机的 QEMU 机器类型，例如 ``q35``。
   * - ``cpu_model``
     - 字符串 / 是
     - 构建虚拟机的 QEMU CPU 模型，例如 ``host``；需要匹配架构和加速方式。
   * - ``playbook``
     - 字符串 / 是
     - 安装文件相对配方目录的路径，通常为 ``provision.yml``；解析后的文件必须位于
       配方目录内且实际存在。
   * - ``variables``
     - 表 / 是
     - 安装变量，见下节；没有变量时保留空的 ``[provision.variables]``。
   * - ``files``
     - 表 / 是
     - 需要从配方目录以外读取的安装文件，见下节；没有文件时保留空的
       ``[provision.files]``。

安装变量与文件
~~~~~~~~~~~~~~

``[provision.variables]`` 的键是配方自己定义的变量名，值必须是字符串。
Ansible 通过 ``cosim_recipe_variables.<变量名>`` 读取它们。软件包版本、内核版本
等安装参数放在这里；目录已经表达的软件版本通过 ``cosim_recipe.software_release``
读取。

``[provision.files]`` 的键是文件别名，值是相对仓库工作区根目录的文件路径，
例如 ``firmware = "third_party/example/firmware.bin"``。路径不能是绝对路径，
不能包含 ``..``，构建输入也不能通过符号链接逃出工作区。
构建器将它转换为绝对路径，以 ``cosim_provision_files.firmware`` 传给 Ansible。
声明文件只是让构建器检查并记录输入，实际复制到哪里由 playbook 的 ``copy`` 步骤决定。

配方自带的脚本、服务和配置直接放在 ``files/``，通过
``{{ playbook_dir }}/files/<文件名>`` 引用。构建器会记录配方源文件和声明输入的内容，
输入变化后重新判断已有镜像是否可以复用。

导出文件：result
~~~~~~~~~~~~~~~~

已安装的磁盘自动产出，无需在 ``result.files`` 中声明。这个列表只声明需要额外
从镜像里复制出来的文件。``[result]`` 可以为空；未声明 ``files`` 时默认为空列表。

.. list-table::
   :header-rows: 1

   * - 字段
     - 类型 / 必填
     - 含义与约束
   * - ``kernel``
     - 字符串 / 否
     - 用作直接启动内核的导出文件名，必须对应某个 ``result.files.name``。
       该文件还会通过 ``readelf`` 检查 ELF 文件头；不导出直接启动内核时省略本字段。
   * - ``files``
     - 对象列表 / 否
     - 用 ``[[result.files]]`` 为每个导出文件添加一项；默认 ``[]``。
   * - ``files[].name``
     - 字符串 / 每项必填
     - 导出后的文件名，所有项之间唯一，只能使用 ASCII 字母、数字、``_``、``.``、
       ``-``；不能使用保留名 ``disk``、``manifest.json``、``packer.log``、``build.log``。
   * - ``files[].guest_path``
     - 字符串 / 每项必填
     - 临时构建虚拟机内的源文件绝对路径，不能包含 ``..``。
       这里的 ``guest`` 只是 QEMU 内部系统的通用称呼。

在 TOML 中声明导出文件后，playbook 还需要执行 ``fetch`` 步骤，见后面的例子。
构建器会检查声明的文件是否全部取回，再验证并发布结果。

TOML 结构示例
~~~~~~~~~~~~~

下面只展示字段组织方式；URL、校验值和外部文件路径需要替换为实际输入：

.. code-block:: toml

   schema = 2

   [base]
   url = "https://example.invalid/base.qcow2"
   sha256 = "0000000000000000000000000000000000000000000000000000000000000000"
   format = "qcow2"

   [provision]
   image_name = "example"
   disk_size = "40000M"
   disk_format = "qcow2"
   cpus = 4
   memory_mb = 8192
   ssh_username = "ubuntu"
   accelerator = "kvm"
   machine_type = "q35"
   cpu_model = "host"
   playbook = "provision.yml"

   [provision.variables]
   package_name = "bash"

   [provision.files]
   firmware = "third_party/example/firmware.bin"

   [result]

   [[result.files]]
   name = "image-os-release"
   guest_path = "/etc/os-release"

.. _ref-vhost-recipe-provision:

provision.yml 写法与字段
------------------------

这个文件使用 Ansible 的 YAML 格式。下面示例安装软件并导出 TOML 中声明的文件；
具体的软件包、驱动和配置步骤由各个配方决定：

.. code-block:: yaml

   - name: Install the image contents
     hosts: default
     become: true
     gather_facts: true
     tasks:
       - name: Install the selected package
         ansible.builtin.package:
           name: "{{ cosim_recipe_variables.package_name }}"
           state: present

       - name: Fetch declared result files
         ansible.builtin.fetch:
           src: "{{ item.guest_path }}"
           dest: "{{ cosim_result_directory }}/{{ item.name }}"
           flat: true
         loop: "{{ cosim_result_files }}"

安装文件的外层字段
~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 字段
     - 本项目中的含义
   * - ``name``
     - 这一组操作的可读名称，显示在构建日志中。
   * - ``hosts``
     - 操作目标。共享构建器使用 ``default`` 表示临时构建虚拟机，
       不是运行构建器的物理主机，也不是拓扑中的 ``vhost`` 字段。
   * - ``become``
     - ``true`` 表示通过提权执行安装操作，通常以 root 身份运行。
   * - ``gather_facts``
     - ``true`` 表示先收集系统信息，例如发行版和架构，供安装步骤检查和使用。
   * - ``tasks``
     - 按顺序执行的安装、配置和文件导出步骤。

这些是 Ansible 的字段；完整定义见
`Ansible playbook 关键字 <https://docs.ansible.com/projects/ansible-core/2.18/reference_appendices/playbooks_keywords.html>`_。

安装步骤中的常用字段
~~~~~~~~~~~~~~~~~~~~

每个步骤用 ``name`` 说明目的，再选择一个 Ansible 模块执行操作。
当前配方常用 ``package`` 或 ``apt`` 安装软件，``file`` 创建目录，
``copy`` 复制文件，``systemd_service`` 启用开机服务，``fetch`` 导出文件。
模块参数按模块自己的定义填写，不是 recipe 增加的另一套字段。

.. list-table::
   :header-rows: 1

   * - 字段或参数
     - 含义
   * - ``package.name`` / ``package.state``
     - 软件包名与目标状态；例如 ``state: present`` 表示确保已安装。
   * - ``file.path`` / ``file.state``
     - 操作的路径和目标状态；例如 ``state: directory`` 创建目录。
   * - ``copy.src`` / ``copy.dest``
     - 本机源文件和虚拟机内的安装路径；``owner``、``group``、``mode`` 设置目标文件
       的属主、属组和权限，权限通常写成 ``"0755"`` 这样的字符串。
   * - ``systemd_service.name`` / ``enabled`` / ``daemon_reload``
     - 服务名、是否启用开机启动、是否重新加载服务配置；启用服务与立即启动服务是两回事。
   * - ``ansible.builtin.user.shell``
     - 创建用户时设置其默认登录 shell，例如 ``/bin/bash``，不表示执行安装脚本。
   * - ``ansible.builtin.command.argv``
     - 要执行的程序和参数列表，例如 ``[dkms, autoinstall]``；不解析管道或重定向。
   * - ``ansible.builtin.shell.cmd``
     - 通过 shell 执行命令字符串，用于确实需要 ``>`` 或管道等语法的步骤。
   * - ``loop`` / ``item``
     - 对列表逐项执行当前步骤，``item`` 是当前项。
   * - ``register``
     - 将步骤的执行结果存入指定变量，后续步骤可以读取 ``stdout`` 等内容。
   * - ``changed_when``
     - 指定何时把步骤报告为发生了修改；不会自动跳过命令，也不会替代失败检查。
   * - ``failed_when``
     - 指定步骤的失败条件；``false`` 可以用于收集诊断信息，但必须另外报告实际失败。
   * - ``block`` / ``rescue``
     - 把步骤分组；组内任务失败时进入 ``rescue``，例如打印 DKMS 日志并最终报错。

普通命令优先使用 ``command.argv``；需要 shell 语法时使用 ``shell.cmd``。
具体行为见 `Ansible command 模块 <https://docs.ansible.com/projects/ansible-core/2.18/collections/ansible/builtin/command_module.html>`_。

项目传入的变量
~~~~~~~~~~~~~~

这些变量由构建器生成；配方读取它们，不另写一份重复配置。

.. list-table::
   :header-rows: 1

   * - 变量
     - 来源和用途
   * - ``cosim_recipe``
     - 目录推导出的 ``distribution``、``release``、``architecture``、``software``、
       ``software_release``，例如用软件版本拼接软件仓库地址。
   * - ``cosim_recipe_variables``
     - ``[provision.variables]`` 的字符串映射。
   * - ``cosim_provision_files``
     - ``[provision.files]`` 的文件别名到构建机绝对路径的映射，供 ``copy.src`` 使用。
   * - ``cosim_result_files``
     - ``[[result.files]]`` 的列表，每项包含 ``name`` 和 ``guest_path``。
   * - ``cosim_result_directory``
     - 本次构建在本机暂存导出文件的目录，供 ``fetch.dest`` 使用；
       成功后文件由构建器移入最终输出目录。
   * - ``playbook_dir``
     - Ansible 提供的变量，指向安装文件所在目录；构建时配方会被复制到临时目录，
       因此配方自带文件应相对这个变量定位。

文件路径与复制方向
~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - 写法
     - 所在位置
     - 用途
   * - ``provision.files.firmware``
     - ``recipe.toml`` 中相对仓库根目录的路径
     - 声明外部安装输入。
   * - ``{{ cosim_provision_files.firmware }}``
     - 运行构建器的本机
     - ``copy.src``：从本机复制到临时构建虚拟机。
   * - ``{{ playbook_dir }}/files/initialize.sh``
     - 本机暂存的配方目录
     - ``copy.src``：复制配方自带文件；此处文件名仅作示例。
   * - ``copy.dest`` / ``fetch.src``
     - 临时构建虚拟机内部
     - 前者是安装目标，后者对应 ``result.files[].guest_path``。
   * - ``{{ cosim_result_directory }}/{{ item.name }}``
     - 运行构建器的本机
     - ``fetch.dest``：取回一个文件，并保留配方声明的输出文件名。

示例中的 ``flat: true`` 让 ``fetch`` 按指定名称保存，
避免额外添加目标机器名称和原始目录层级；行为见
`Ansible fetch 模块 <https://docs.ansible.com/projects/ansible-core/2.18/collections/ansible/builtin/fetch_module.html>`_。

使用镜像
--------

vHost 直接选择配方：

.. code-block:: yaml

   vhost:
     use: vhost-x86
     image: ubuntu/24.04/x86_64/rocm/7.0
     cmdline: console=ttyS0 root=/dev/vda1 rw
     root_bus: virtio

运行时，启动器解析已验证的配方产物；如果声明了 ``result.kernel``，就用对应文件
直接启动，并将镜像磁盘作为 ``root`` 磁盘挂载。未导出内核时由 QEMU 使用磁盘启动流程。
不使用配方的 vHost 也可以直接声明 ``kernel``、``initrd``、``cmdline`` 和 ``disks``。
使用 ``cmdline`` 时需要直接启动内核。完整运行字段见 :ref:`ref-topology-schema`。

命令
----

.. code-block:: bash

   just ci-rocm-assets list
   just ci-rocm-assets inspect <配方标识>
   just ci-rocm-assets validate <配方标识>
   just ci-rocm-assets build <配方标识>

``inspect`` 读取当前配置和缓存状态；``validate`` 检查 Packer 与 Ansible 配置；
``build`` 构建镜像，或复用通过输入和完整性检查的现有镜像。
构建结果位于 ``build/images/<配方标识>/``：``disk`` 是已安装的磁盘，
其他导出文件沿用 ``result.files[].name``，``manifest.json`` 是构建器生成的记录，
保存配方标识、输入指纹及产物的大小和 SHA-256。它们都不属于源码。

相关页面
--------

- 新增配方流程：:ref:`contrib-add-vhost-recipe`
- 运行机器字段：:ref:`ref-topology-schema`
- 开机后的 GPU 初始化：:ref:`ref-guest-parameters`
- 文件和产物路径：:doc:`files_and_artifacts`

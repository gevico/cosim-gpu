.. SPDX-License-Identifier: Apache-2.0

.. _gs-install:

安装与构建
==========

本页给出获取源码、初始化子模块并构建 QEMU、gem5、客户机资产和 Rust launcher
的默认命令。主机依赖与容器差异见 :doc:`platforms/linux` 与
:doc:`platforms/container`。

获取源码与子模块
----------------

.. code-block:: bash

   git clone https://github.com/gevico/cosim-gpu.git
   cd cosim-gpu
   just dev-submodules

``just dev-submodules`` 初始化 ``qemu``、``gem5`` 和 ``gem5-resources`` 三个
子模块。QEMU 与 gem5 的源码分别由各自子模块提供，联合仿真不额外打补丁。

选择构建环境
------------

构建 recipe 通过 ``scripts/host/dev.sh`` 在主机或临时开发容器中执行，由环境变量
``COSIM_ENV`` 选择：Linux 默认 ``host``，其他系统默认 ``container``。

.. code-block:: bash

   just dev-image                  # 非 Linux 主机或缺少构建依赖时执行一次
   export COSIM_ENV=container      # 让后续构建在容器中进行

开发容器的内容、挂载方式与限制见 :doc:`platforms/container`。

一键构建
--------

.. code-block:: bash

   just build-all

``just build-all`` 依次执行下列 recipe：

.. list-table::
   :header-rows: 1

   * - recipe
     - 产物
   * - ``just build-qemu``
     - ``build/qemu/qemu-system-x86_64``，带 ``vfio-user-pci`` 与 KVM 支持
   * - ``just build-gem5``
     - ``build/gem5/<arch>/VEGA_X86/gem5.opt``
   * - ``just build-disk``
     - ``build/rocm-local-installed/{disk,kernel}``
   * - ``just build-gpu-app``
     - ``build/apps/square/square.default``
   * - ``just build-cosim``
     - Rust ``cosim`` launcher

客户机镜像构建需要 QEMU，GPU 应用构建在独立的 GPU 容器中进行。

分步构建
--------

首次构建耗时长，可以按组件重试：

.. code-block:: bash

   just build-qemu                 # 使用全部 CPU
   just build-qemu 4               # 限制并行任务数
   just build-gem5                 # 使用全部 CPU
   just build-gem5 1               # 链接阶段内存不足时限制并行度
   just build-disk                 # 需要 /dev/kvm、QEMU 与约 60 GB 空间
   just build-cosim

``just build-gem5`` 的并行度默认等于 CPU 核数；被 OOM 杀死时把并行度降到 1。

客户机资产
----------

``just build-disk`` 产出的内核与磁盘是成对的，必须一起使用。镜像内容、构建
流程、产物清单与校验方式见 :doc:`guest_image`。

验证构建结果
------------

.. code-block:: bash

   just run-cli validate resources/machines/single-gpu.yaml \

   ls -l build/qemu/qemu-system-x86_64
   ls -l build/gem5/*/VEGA_X86/gem5.opt
   ls -l build/rocm-local-installed/disk build/rocm-local-installed/kernel

``validate`` 只检查拓扑与 vHost；带 ``--assets`` 时还会检查本机输入文件。

相关页面
--------

- :doc:`guest_image`
- :doc:`first_session`
- :doc:`platforms/linux`
- :doc:`platforms/container`
- :ref:`产物、路径与源码地图 <ref-files-and-artifacts>`

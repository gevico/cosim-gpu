.. SPDX-License-Identifier: Apache-2.0


.. _topo-machines-aarch64:

AArch64 样例系列
================

仓库里有 3 个 AArch64 单机样例，本页作为系列页统一说明：host-only-aarch64、gem5-aarch64 与 qemu-device-aarch64。三者都使用 ``vhost-arm-tcg`` 主机；原生执行架构是 AArch64，而 gem5 构建目标仍是 ``VEGA_X86``\ 。随仓库提供的 Ubuntu/ROCm 客户机镜像只面向 x86_64，因此这些样例用于主机链路、计划渲染与原生 ARM64 的 gem5 进程，不用于启动客户机。

三个样例
--------

.. list-table::
   :header-rows: 1

   * - 样例
     - 主机
     - 设备
     - 内存池
     - 说明
   * - ``host-only-aarch64``
     - ``vhost-arm-tcg``\ （暂停），64 MiB，1 vCPU
     - 无
     - 64 MiB
     - AArch64 主机基础链路
   * - ``gem5-aarch64``
     - ``vhost-arm-tcg``\ （暂停），512 MiB，1 vCPU
     - 1 × ``mi300x-aarch64``\ ，1 GiB VRAM，4 CU
     - 1.5 GiB
     - 原生 ARM64 gem5 构建
   * - ``qemu-device-aarch64``
     - ``vhost-arm-tcg``\ （暂停），64 MiB，1 vCPU
     - 1 × ``qemu-edu-aarch64``\ （id 为 ``edu``\ ）
     - 64 MiB
     - 依赖 AArch64 构建产物

host-only-aarch64 机器
----------------------

``resources/machines/host-only-aarch64.yaml`` 从 ``vhosts/qemu.yaml`` 与 ``vhosts/vhost-arm-tcg.yaml`` 导入，只声明一台暂停的 AArch64 主机，用于 AArch64 上的会话基础链路。

.. code-block:: bash

   just run-cli validate resources/machines/host-only-aarch64.yaml
   just run-topology resources/machines/host-only-aarch64.yaml --dry-run
   just run-topology-dev resources/machines/host-only-aarch64.yaml --run-for 1

- 机器数量：1（``m0``\ ）；一个 vHost，无设备。
- 内存池 64 MiB；主机二进制 ``qemu-system-aarch64`` 从 ``PATH`` 查找。

gem5-aarch64 机器
-----------------

``resources/machines/gem5-aarch64.yaml`` 组合一个暂停的 ARM64 主机和一个原生 ARM64 gem5 MI300X 进程：

- 主机覆盖 ``runtime.binary`` 为 ``build/qemu/qemu-system-aarch64``\ ，内存 512 MiB。
- 设备使用 ``mi300x-aarch64`` 模板：二进制为 ``build/gem5/aarch64/VEGA_X86/gem5.opt``\ ，VRAM 覆盖为 1 GiB，``num_compute_units`` 为 4。
- 设备显式 id 为 ``gpu0``\ ，其区域名为 ``gpu0.vram``\ ，位于 512 MiB；内存池 1.5 GiB。
- 仓库未提供 AArch64 客户机镜像，因此该 vHost 不声明镜像或内核。

.. code-block:: bash

   just run-cli validate resources/machines/gem5-aarch64.yaml
   just run-topology resources/machines/gem5-aarch64.yaml --dry-run

qemu-device-aarch64 机器
------------------------

``resources/machines/qemu-device-aarch64.yaml`` 与 x86_64 的 :doc:`qemu_device` 对应：一台暂停的 AArch64 主机通过 vfio-user 连接 QEMU ``edu`` 设备。

- 主机覆盖 ``runtime.binary`` 为 ``build/qemu/qemu-system-aarch64``\ 。
- 设备使用 ``qemu-edu-aarch64`` 模板，显式 id 为 ``edu``\ ；没有私有内存区域。
- 内存池 64 MiB；x86_64 与 AArch64 的主机、设备二进制都需要带 vfio-user 支持的 QEMU。

.. code-block:: bash

   just run-cli validate resources/machines/qemu-device-aarch64.yaml
   just run-topology resources/machines/qemu-device-aarch64.yaml --dry-run

共同约束
--------

- ``just build-qemu`` 按宿主架构构建（``COSIM_HOST_ARCH``\ ，默认取当前架构）；AArch64 样例需要
  AArch64 主机上构建的 ``build/qemu/qemu-system-aarch64``\ ，gem5 二进制同理。
- ``just build-gem5`` 的产物目录是 ``build/gem5/<host_arch>/VEGA_X86``\ ；gem5 构建目标始终是 ``VEGA_X86``\ ，只有原生执行架构不同。
- 没有 AArch64 客户机镜像：这些 vHost 不能启动客户机系统。
- ``vhost-arm``\ （KVM、``virt,gic-version=3``\ ）模板存在，但仓库样例只引用 ``vhost-arm-tcg``\ 。
- 架构相关测试在 AArch64 上选择 ``vhost-arm-tcg``\ ；全部样例由 render 测试加载。

相关页面
--------

- vHost 配置：:doc:`../hosts/index`
- 设备目录：:doc:`../devices/index`
- 编写拓扑：:doc:`../write_topology`
- 多机 AArch64 样例：:doc:`../multi_machine`
- 机器目录：:doc:`index`
- 源码：``resources/machines/host-only-aarch64.yaml``\ 、``resources/machines/gem5-aarch64.yaml``\ 、``resources/machines/qemu-device-aarch64.yaml``

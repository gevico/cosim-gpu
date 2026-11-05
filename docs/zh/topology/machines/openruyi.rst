.. SPDX-License-Identifier: Apache-2.0

.. _topo-machine-openruyi:

openRuyi RISC-V vHost
=====================

采用官方 openRuyi Server 2026.09 RVA23 QCOW2 镜像，直接加载内核并使用 VirtIO 根磁盘。
在 x86_64 Linux 主机上使用 QEMU TCG、AIA 和 Sv48 运行 RISC-V vHost。
机器保持 4 GiB 内存、4 GiB 显存、两个 vCPU 和四个 CU。

构建与运行
----------

在仓库根目录执行，首次构建需要网络连接：

.. code-block:: bash

    just build-qemu 2 riscv64
    just build-gem5 1
    just build-rocm-assets openruyi/2026.09/riscv64/rocm/7.2.4

recipe 位于 ``resources/images/recipes/``，沿用 Ubuntu 的 Packer/Ansible 构建流程。
校验基础镜像的 SHA-256 后，通过 openRuyi DNF 仓库安装原生 ROCm 7.2.4、hipcc、
Clang 22、GCC 16、开发库和 rocm-smi，并导出软件包及编译器版本记录。
HIP 程序在 vHost 内编译。

基础 QCOW2 提供 EFI 引导程序。Packer 使用 QEMU 随附的 EDK II 固件启动该磁盘并
安装软件。recipe 将安装好的内核、软件包及编译器记录导出到 QCOW2
磁盘所在的 bundle 目录。

``vhost.image`` 校验并复用发布于
``build/images/openruyi/2026.09/riscv64/rocm/7.2.4/`` 的 bundle。仿真会话通过 QEMU
自带的 OpenSBI 固件及 ``-kernel`` 启动，并使用 ``root=/dev/vda2``
挂载 VirtIO 根磁盘。Linux 分配 GPU PCI BAR，amdgpu 从 ROM BAR 读取 VBIOS。

交互使用
--------

选择一个尚不存在的运行目录：

.. code-block:: bash

    just run-topology resources/machines/openruyi-gpu.yaml \
      --run-dir build/openruyi-session --pool-dir build/openruyi-session/memory \
      --ready-timeout 900

连接 ``build/openruyi-session/m0/serial.sock``，使用官方 Server 账号
``root`` / ``openruyi`` 登录：

.. code-block:: sh

    modprobe amdgpu
    rocm-smi
    rocm-smi --showid --showbus --showmeminfo vram
    hipcc --offload-arch=gfx942 -O2 program.hip -o program
    ./program

recipe 提供模型专用 modprobe 参数，并在登录环境设置编译器路径。
启动器为每次仿真创建独立的磁盘 overlay。

以上命令使用磁盘共享池。除镜像和 overlay 外，至少预留 8 GiB 磁盘空间用于共享池。
启动器退出时清理共享池，保留日志。

rocm-smi 中未建模的温度、功耗和风扇数据可能显示 N/A。

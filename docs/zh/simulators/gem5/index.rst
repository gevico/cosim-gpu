.. SPDX-License-Identifier: Apache-2.0

.. _sim-gem5-index:

gem5 的定位：性能仿真
======================

gem5 在本项目中负责 MI300X 的性能仿真。它不运行客户机内核，而是构建一个只包含 GPU 模型与 Ruby 内存层次的最小系统，通过 vfio-user 接收来自 host QEMU 的 PCI 访问。

运行形态
---------

- 构建目标是 ``VEGA_X86``\ ，产物为原生可执行的 ``build/gem5/<native>/VEGA_X86/gem5.opt``\ 。
- 配置脚本 ``resources/devices/gpu/mi300x/gem5.py``\ 创建最小 ``System``\ 、占位 ``AtomicSimpleCPU``\ 和 ``StubWorkload``\ ，因此 gem5 侧不需要 x86 内核。
- GPU 缓存与内存层次使用 ``Disjoint_VIPER``\ 协议；QEMU 与 gem5 共享同一份客户机内存与 VRAM 文件。
- YAML 适配器每个进程只启动一个 GPU；单进程多 GPU 与 XGMI 只存在于直接调用 gem5 的路径，见 :doc:`multi_gpu_xgmi`\ 。

本章内容
---------

.. toctree::
   :maxdepth: 1

   mi300x_pci
   mi300x_model
   address_translation
   multi_gpu_xgmi

推荐阅读路径
-------------

- 从 :doc:`mi300x_pci`\ 开始了解设备如何被 QEMU 枚举。
- 然后读 :doc:`mi300x_model`\ 了解命令、DMA 与中断路径。
- 地址翻译细节见 :doc:`address_translation`\ 。
- 多 GPU、XGMI 与 SST 事实见 :doc:`multi_gpu_xgmi`\ 。

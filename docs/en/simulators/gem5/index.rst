.. SPDX-License-Identifier: Apache-2.0

.. _sim-gem5-index:

gem5 performance simulation
============================

gem5 provides performance simulation of the MI300X in this project. It does not run a guest kernel; instead it builds a minimal system containing only the GPU model and the Ruby memory hierarchy and receives PCI accesses from the host QEMU over vfio-user.

Run Shape
----------

- The build target is ``VEGA_X86`` and the artifact is the native ``build/gem5/<native>/VEGA_X86/gem5.opt``.
- The configuration script ``resources/devices/gpu/mi300x/gem5.py`` creates a minimal ``System``, a placeholder ``AtomicSimpleCPU`` and ``StubWorkload``, so no x86 kernel is needed on the gem5 side.
- The GPU caches and memory hierarchy use the ``Disjoint_VIPER`` protocol, and QEMU and gem5 share the same guest memory and VRAM files.
- The YAML adapter starts one GPU per process; single-process multi-GPU and XGMI exist only on the direct gem5 invocation path, described in :doc:`multi_gpu_xgmi`.

Chapter Contents
-----------------

.. toctree::
   :maxdepth: 1

   mi300x_pci
   mi300x_model
   address_translation
   multi_gpu_xgmi

Recommended Reading Path
-------------------------

- Start with :doc:`mi300x_pci` to see how QEMU enumerates the device.
- Then read :doc:`mi300x_model` for the command, DMA and interrupt paths.
- Address translation details are in :doc:`address_translation`.
- Multi-GPU, XGMI and SST facts are in :doc:`multi_gpu_xgmi`.

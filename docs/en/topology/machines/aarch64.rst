.. SPDX-License-Identifier: Apache-2.0


.. _topo-machines-aarch64:

AArch64 samples
===============

The repository has three AArch64 single-machine samples, described together on this series page: host-only-aarch64, gem5-aarch64 and qemu-device-aarch64. All three use the ``vhost-arm-tcg`` host. The native execution architecture is AArch64 while the gem5 build target is still ``VEGA_X86``. The Ubuntu/ROCm guest image shipped with the repository targets x86_64 only, so these samples cover host plumbing, plan rendering and the native ARM64 gem5 process, not a booting guest.

The three samples
-----------------

.. list-table::
   :header-rows: 1

   * - Sample
     - Host
     - Devices
     - Memory pool
     - Notes
   * - ``host-only-aarch64``
     - ``vhost-arm-tcg`` (paused), 64 MiB, 1 vCPU
     - None
     - 64 MiB
     - AArch64 host plumbing
   * - ``gem5-aarch64``
     - ``vhost-arm-tcg`` (paused), 512 MiB, 1 vCPU
     - 1 × ``mi300x-aarch64``, 1 GiB VRAM, 4 CU
     - 1.5 GiB
     - Native ARM64 gem5 build
   * - ``qemu-device-aarch64``
     - ``vhost-arm-tcg`` (paused), 64 MiB, 1 vCPU
     - 1 × ``qemu-edu-aarch64`` (id ``edu``)
     - 64 MiB
     - Depends on AArch64 build artifacts

host-only-aarch64 machine
-------------------------

``resources/machines/host-only-aarch64.yaml`` imports from ``vhosts/qemu.yaml`` and ``vhosts/vhost-arm-tcg.yaml`` and declares a single paused AArch64 host for AArch64 session plumbing.

.. code-block:: bash

   just run-cli validate resources/machines/host-only-aarch64.yaml
   just run-topology resources/machines/host-only-aarch64.yaml --dry-run
   just run-topology-dev resources/machines/host-only-aarch64.yaml --run-for 1

- Machine count: one (``m0``); one vHost and no devices.
- The 64 MiB pool; the host binary ``qemu-system-aarch64`` is looked up in ``PATH``.

gem5-aarch64 machine
--------------------

``resources/machines/gem5-aarch64.yaml`` combines a paused ARM64 host with one native ARM64 gem5 MI300X process:

- The host overrides ``runtime.binary`` to ``build/qemu/qemu-system-aarch64`` and sets memory to 512 MiB.
- The device uses the ``mi300x-aarch64`` template: binary ``build/gem5/aarch64/VEGA_X86/gem5.opt``, VRAM overridden to 1 GiB, and ``num_compute_units`` set to 4.
- The explicit device id is ``gpu0``, its region is ``gpu0.vram`` at 512 MiB, and the pool is 1.5 GiB.
- The vHost has no image or kernel because no AArch64 guest image is shipped.

.. code-block:: bash

   just run-cli validate resources/machines/gem5-aarch64.yaml
   just run-topology resources/machines/gem5-aarch64.yaml --dry-run

qemu-device-aarch64 machine
---------------------------

``resources/machines/qemu-device-aarch64.yaml`` mirrors the x86_64 :doc:`qemu_device`: a paused AArch64 host connects to a QEMU ``edu`` device over vfio-user.

- The host overrides ``runtime.binary`` to ``build/qemu/qemu-system-aarch64``.
- The device uses the ``qemu-edu-aarch64`` template with the explicit id ``edu``; it has no private memory region.
- The pool is 64 MiB; both the x86_64 and AArch64 host and device binaries need a QEMU built with vfio-user support.

.. code-block:: bash

   just run-cli validate resources/machines/qemu-device-aarch64.yaml
   just run-topology resources/machines/qemu-device-aarch64.yaml --dry-run

Shared constraints
------------------

- ``just build-qemu`` builds for the host architecture (``COSIM_HOST_ARCH``, defaulting to the current architecture); the AArch64 samples need ``build/qemu/qemu-system-aarch64`` and the gem5 binary built on an AArch64 host.
- ``just build-gem5`` writes its output under ``build/gem5/<host_arch>/VEGA_X86``; the gem5 build target is always ``VEGA_X86`` and only the native execution architecture differs.
- There is no AArch64 guest image: these vHosts cannot boot a guest OS.
- The ``vhost-arm`` template (KVM, ``virt,gic-version=3``) exists, but the repository samples reference only ``vhost-arm-tcg``.
- Architecture-dependent tests select ``vhost-arm-tcg`` on AArch64; every sample is loaded by the render test.

Related pages
-------------

- vHost profiles: :doc:`../hosts/index`
- Device catalog: :doc:`../devices/index`
- Writing topologies: :doc:`../write_topology`
- Multi-machine AArch64 samples: :doc:`../multi_machine`
- Machine catalog: :doc:`index`
- Sources: ``resources/machines/host-only-aarch64.yaml``, ``resources/machines/gem5-aarch64.yaml``, ``resources/machines/qemu-device-aarch64.yaml``

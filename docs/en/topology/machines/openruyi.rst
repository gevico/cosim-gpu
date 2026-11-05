.. SPDX-License-Identifier: Apache-2.0

.. _topo-machine-openruyi:

openRuyi RISC-V vHost
=====================

Use the official openRuyi Server 2026.09 RVA23 QCOW2 image with direct kernel boot and a
VirtIO root disk. QEMU TCG runs the RISC-V vHost on an x86_64 Linux host with
AIA and Sv48. The machine uses 4 GiB RAM, 4 GiB VRAM, two vCPUs, and four CUs.

Build and run
-------------

From the repository root, with network access for the first build:

.. code-block:: bash

    just build-qemu 2 riscv64
    just build-gem5 1
    just build-rocm-assets openruyi/2026.09/riscv64/rocm/7.2.4

The recipe follows the same Packer/Ansible workflow as the Ubuntu recipe under
``resources/images/recipes/``. It verifies the base image's SHA-256, installs
native ROCm 7.2.4, hipcc, Clang 22, GCC 16, development libraries, and rocm-smi
through
openRuyi's DNF repositories, and exports package and compiler version records.
HIP programs are compiled inside the vHost.

The base QCOW2 provides an EFI bootloader. Packer boots this disk with QEMU's
bundled EDK II firmware to install the software. The recipe exports the installed
kernel and package and compiler records beside the QCOW2 disk.

``vhost.image`` verifies and reuses the bundle published under
``build/images/openruyi/2026.09/riscv64/rocm/7.2.4/``. Simulation sessions use
QEMU's OpenSBI firmware with ``-kernel`` and mount the VirtIO
root disk with ``root=/dev/vda2``. Linux allocates the GPU's PCI BARs and amdgpu
reads the VBIOS from its ROM BAR.

Interactive use
---------------

Choose a run directory that does not yet exist:

.. code-block:: bash

    just run-topology resources/machines/openruyi-gpu.yaml \
      --run-dir build/openruyi-session --pool-dir build/openruyi-session/memory \
      --ready-timeout 900

Connect to ``build/openruyi-session/m0/serial.sock`` and log in with the official
Server credentials, ``root`` / ``openruyi``:

.. code-block:: sh

    modprobe amdgpu
    rocm-smi
    rocm-smi --showid --showbus --showmeminfo vram
    hipcc --offload-arch=gfx942 -O2 program.hip -o program
    ./program

The recipe supplies model-specific modprobe options and sets the compiler path
in the login environment.
The launcher uses a fresh disk overlay for each session.

The command above uses a disk-backed shared pool. Allow at least 8 GiB disk
space for the pool in addition to the image and its overlay. Launcher shutdown
removes the pool and preserves logs.

Unmodeled thermal, power, and fan telemetry can report N/A in rocm-smi.

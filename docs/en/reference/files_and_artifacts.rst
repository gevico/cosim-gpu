.. SPDX-License-Identifier: Apache-2.0

.. _ref-files-and-artifacts:

Files and artifacts
===================

This page is the single source of truth for repository directories, build artifacts, session directories, guest image files and path-related environment variables. Version and provenance data is in :doc:`version_matrix`.

Source directories
------------------

.. list-table::
   :header-rows: 1

   * - Path
     - Content
     - Notes
   * - ``crates/cosim-topology/src/``
     - YAML decoding, validation, template merging, memory layout, adapters and command rendering
     - Rust library exposing ``load``, ``graph`` and ``schema``
   * - ``crates/cosim-runtime/src/``
     - Execution plans, process supervision, resource ownership, disks and cleanup
     - Rust library exposing ``plan``, ``run`` and ``clean``
   * - ``crates/cosim-cli/src/``
     - Command line, signal handling, events and verdict output
     - the ``cosim`` executable
   * - ``crates/*/tests/``
     - Topology rendering, session lifecycle and vfio-user integration tests
     - tests that need QEMU or gem5 are marked ``--ignored``
   * - ``resources/vhosts/``, ``resources/devices/``
     - Reusable vHost and device-model configurations
     - imported by machine configurations
   * - ``resources/machines/``, ``resources/clusters/``
     - Complete machine configurations and multi-machine compositions
     - tests load configurations and render every process
   * - ``samples/``
     - Reserved for example programs run after a vHost boots
     - topology YAML lives under ``resources/``
   * - ``scripts/``
     - Build, development container, launchers, test runners and image helper scripts
     - ``cosim_launch.sh`` is the legacy shell launcher
   * - ``scripts/ci/``
     - CI lifecycle, ROCm regression, image and runtime artifact tools
     - see the ``ci-*`` and ``scripts/ci/test_*.py`` recipes in ``justfile``
   * - ``resources/images/recipes/``
     - Guest image recipes (Packer template and Ansible playbook)
     - the only recipe is ``ubuntu/24.04/x86_64/rocm/7.0/``
   * - ``third_party/gem5/src/dev/amdgpu/``
     - MI300X device model, vfio-user server, GART/PM4/SDMA/IH
     - content of the gem5 submodule
   * - ``third_party/gem5/configs/example/gpufs/``
     - cosim gem5 configuration
     - ``mi300_cosim.py`` is started by the device adapter
   * - ``configs/sst/``
     - SST network experiment data models
     - independent of the Rust launcher
   * - ``ext/libvfio-user/``
     - vfio-user transport library
     - a dependency of the gem5 submodule
   * - ``third_party/qemu/hw/remote/vfio-user-obj.c``, ``third_party/qemu/hw/vfio-user/``
     - QEMU vfio-user server and client implementation
     - content of the QEMU submodule
   * - ``docs/``
     - Bilingual documentation sources
     - Chinese primary, English file-by-file mirror

Build artifacts
---------------

The build recipes map to the following artifacts; version data is in :doc:`version_matrix`.

.. list-table::
   :header-rows: 1

   * - Artifact
     - Path
     - Recipe
   * - QEMU
     - ``build/qemu/qemu-system-<arch>``
     - ``just build-qemu``
   * - gem5
     - ``build/gem5/<arch>/VEGA_X86/gem5.opt``
     - ``just build-gem5``
   * - Guest kernel
     - ``build/rocm-local-installed/kernel``
     - ``just build-disk``
   * - Guest disk
     - ``build/rocm-local-installed/disk`` (about 55 GB)
     - ``just build-disk``
   * - ROCm asset bundle
     - ``build/rocm-assets/`` (kernel, disk, ``manifest.json`` and related files)
     - ``just build-rocm-assets``
   * - Rust launcher
     - ``build/cargo/{host,container}/release/cosim``
     - ``just build-cosim``
   * - Sample GPU program
     - ``build/apps/<name>/<name>.default`` (default ``square``)
     - ``just build-gpu-app``

Session directories and runtime artifacts
-----------------------------------------

``cosim run`` creates an independent directory and resources for every machine; the common paths are:

.. list-table::
   :header-rows: 1

   * - Path
     - Content
     - Lifetime
   * - ``.cosim/<name>/``
     - run directory: ``plan.json``, ``options.json``, ``manifest.json``, per-machine ``layout.json``, process ``output.log``, serial logs and ``verdict.json``
     - kept after a normal exit; ``cosim clean <run-dir>`` releases resources after an abnormal exit
   * - ``<run-dir>/session.lock``
     - session lock; the launcher and all child processes hold the same lock
     - released after every process exits
   * - ``/dev/shm/cosim-<name>-<hash>``
     - pool directory on Linux with one ``pool`` file per machine; other systems use ``<run-dir>/memory``
     - removed after a normal exit
   * - ``<run>/<machine>/<device>.sock``
     - vfio-user socket served by the device to the host
     - removed on exit
   * - ``<run>/<machine>/``
     - per-machine qcow2 disk overlays (``<disk>.qcow2``)
     - removed on exit
   * - ``~/.cache/cosim-gpu/disk-locks``
     - shared disk image lease directory (``COSIM_DISK_LOCK_DIR``)
     - lock files remain after the session
   * - ``artifacts/standalone/<run-id>/``
     - diagnostic artifact directory captured by the legacy shell launcher
     - managed by the launcher cleanup path

Guest image files
-----------------

The guest image is built from the only recipe and its driver initialization depends on these files.

.. list-table::
   :header-rows: 1

   * - Path (inside the guest)
     - Purpose
   * - ``/root/roms/mi300.rom``
     - VGA BIOS ROM binary written to ``0xC0000`` by ``dd``
   * - ``/usr/lib/firmware/amdgpu/mi300_discovery``
     - IP discovery firmware
   * - ``/usr/lib/firmware/amdgpu/ip_discovery.bin``
     - symbolic link to ``mi300_discovery``
   * - ``/lib/systemd/system/cosim-gpu-initialize.service``
     - boot-time initialization unit
   * - ``/usr/local/bin/cosim-gpu-initialize.sh``
     - initialization script: ROM write, firmware link, driver load and verification
   * - ``/lib/modules/$(uname -r)/updates/dkms/amdgpu.ko.zst``
     - ROCm 7.0 DKMS amdgpu kernel module

gem5 MI300X model sources
-------------------------

.. list-table::
   :header-rows: 1

   * - File (``third_party/gem5/src/dev/amdgpu/``)
     - Purpose
   * - ``mi300x_vfio_user.{cc,hh}``
     - vfio-user server SimObject exporting BARs, config space and interrupts
   * - ``MI300XVfioUser.py``
     - Python wrapper for the vfio-user SimObject
   * - ``cosim_bridge.hh``
     - CosimBridge interface used by the vfio-user server
   * - ``amdgpu_device.cc``
     - GPU device core: ``readROM()``, ``intrPost()`` and ``writeFrame()``
   * - ``amdgpu_vm.{cc,hh}``
     - GART, AGP, MMHUB and user-context translation with the shared-VRAM fallback
   * - ``pm4_packet_processor.{cc,hh}``
     - PM4 decoding, DMA routing, VRAM write routing and ``isVRAMAddress()``
   * - ``pm4_defines.hh``
     - PM4 opcodes including ``IT_ACQUIRE_MEM`` and ``IT_SET_RESOURCES``
   * - ``sdma_engine.{cc,hh}``
     - SDMA execution, rptr writeback routing and the ``sdma_delay`` parameter
   * - ``interrupt_handler.cc``
     - IH ring DMA and MSI-X interrupt delivery
   * - ``amdgpu_nbio.cc``
     - ASIC initialization complete register

gem5 configuration, Python components and QEMU interface
--------------------------------------------------------

.. list-table::
   :header-rows: 1

   * - File
     - Purpose
   * - ``third_party/gem5/configs/example/gpufs/mi300_cosim.py``
     - vfio-user cosim system configuration started by the ``gem5-mi300x`` adapter
   * - ``src/python/third_party/gem5/components/devices/gpus/amdgpu.py``
     - MI300X device definition
   * - ``third_party/qemu/hw/remote/vfio-user-obj.c``
     - QEMU device-side vfio-user object implementation

Path-related environment variables
----------------------------------

.. list-table::
   :header-rows: 1

   * - Variable
     - Purpose
     - Default
   * - ``COSIM_WORKSPACE``
     - workspace root used to resolve resource paths
     - repository root (set by ``scripts/host/dev.sh``)
   * - ``COSIM_DISK_LOCK_DIR``
     - disk image lease directory
     - ``~/.cache/cosim-gpu/disk-locks``
   * - ``COSIM_ENV``
     - runs build and check recipes on the host or in a temporary container
     - ``host`` on Linux, ``container`` elsewhere
   * - ``COSIM_DEV_IMAGE``
     - development container image name
     - ``cosim-dev:local``
   * - ``COSIM_HOST_ARCH``
     - build and execution architecture
     - current host architecture, ``x86_64`` or ``aarch64``
   * - ``GEM5_BUILD_DIR``
     - gem5 build directory
     - ``build/gem5/<arch>/VEGA_X86``
   * - ``COSIM_STDIN_LIFELINE``
     - ends the session when standard input closes
     - set to ``1`` by ``scripts/host/dev.sh``
   * - ``COSIM_RUN_ID``
     - legacy shell launcher session identifier used to derive socket and shared-memory names
     - generated by ``scripts/host/cosim_launch.sh``
   * - ``GPU_APP_BUILD_IMAGE``
     - build image for guest GPU test programs
     - ``ghcr.io/third_party/gem5/gpu-fs:latest``

Sources and maintenance
-----------------------

The path and file lists follow the current repository layout; update this page when files move:

- Build artifact paths are defined by ``justfile`` and ``scripts/host/build.sh``.

- Session paths and reserved names are defined by ``crates/cosim-runtime/src/layout.rs``.

- Guest file paths are defined by ``provision.yml`` and ``files/`` in the image recipe.

- Environment variables are defined by ``justfile``, ``scripts/host/dev.sh``, ``scripts/host/cosim_launch.sh`` and ``crates/cosim-runtime/src/env.rs``.

Verify with:

.. code-block:: bash

   just --list
   just build-status
   just run-topology resources/machines/single-gpu.yaml --dry-run

Related pages
-------------

- Versions, image tags and provenance: :doc:`version_matrix`

- Guest driver parameters: :doc:`guest_parameters`

- Legacy shell launcher options: :doc:`legacy_launcher_flags`

- Install and build: :ref:`gs-install`

- Session lifecycle: :ref:`launcher-session-lifecycle`

- Session debugging and verdicts: :ref:`launcher-debugging-sessions`

- CI and artifact reuse: :ref:`contrib-ci`

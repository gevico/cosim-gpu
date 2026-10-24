.. SPDX-License-Identifier: Apache-2.0

.. _ref-version-matrix:

Version matrix
==============

This page is the single source of truth for versions and images. Every record distinguishes a recorded value, a minimum version and the way to verify it: recorded values reproduce a run, minimum versions decide compatibility, and the verification method tells you how to check the working tree.

Component versions
------------------

.. list-table::
   :header-rows: 1

   * - Component
     - Version or value
     - Type
     - Evidence
   * - QEMU (recorded submodule)
     - v11.1.2, commit ``4fc49f46``
     - recorded
     - ``third_party/qemu/VERSION``; ``git ls-tree HEAD qemu``
   * - QEMU (system fallback, legacy launcher)
     - 10.1 or newer with ``vfio-user-pci``
     - minimum
     - preflight check in ``scripts/host/cosim_launch.sh``
   * - gem5 (submodule)
     - ``gevico/gem5`` branch ``gevico/cosim-gpu``; current checkout ``v25.0.0.0-961-gcc9d5dd248``
     - recorded
     - ``git submodule status gem5``; ``git -C gem5 describe --tags --always``
   * - gem5 build target
     - ``VEGA_X86``
     - fixed
     - ``gem5_build_dir`` in ``justfile``
   * - GPU model
     - MI300X, gfx942, PCI ``0x1002`` and ``0x74a0``
     - fixed
     - ``resources/devices/gpu/mi300x.yaml``
   * - Coherence protocol
     - ``GPU_VIPER``
     - fixed
     - ``third_party/gem5/configs/example/gpufs/Disjoint_VIPER.py``
   * - Rust
     - 1.95 or newer
     - minimum
     - ``rust-version`` in ``Cargo.toml``
   * - Guest operating system
     - Ubuntu 24.04.2 LTS
     - recorded
     - image ``recipe.toml``
   * - Guest kernel
     - ``6.8.0-124-generic``
     - recorded
     - image ``recipe.toml``
   * - ROCm
     - 7.0 (apt repositories ``amdgpu/7.0`` and ``rocm/apt/7.0``)
     - recorded
     - ``provision.yml``
   * - amdgpu DKMS
     - matches ROCm 7.0
     - recorded
     - ``provision.yml``
   * - PyTorch wheel channel
     - ``rocm6.0``
     - recorded
     - ``provision.yml`` (channel pinned inside the image)
   * - Guest ROM and discovery firmware
     - ``mi200.rom``, ``mi300.rom``, ``mi300_discovery``, ``mi350_discovery``
     - recorded
     - ``provision.yml``; files under the image recipe ``files/``
   * - Packer
     - 1.16.1
     - recorded
     - image ``build.sh``
   * - Packer plugins
     - qemu 1.1.7, ansible 1.1.6
     - recorded
     - image ``image.pkr.hcl``

The QEMU submodule record is the v11.1.2 release commit. The ``qemu`` checkout in a working tree may sit on another branch, so use ``git -C qemu describe --tags --always`` before building; the QEMU version in release notes refers to the recorded gitlink.

Images and containers
---------------------

.. list-table::
   :header-rows: 1

   * - Name
     - Role
     - Source
   * - ``cosim-dev:local``
     - development container image; also the default gem5 container image of the legacy shell launcher
     - ``just dev-image`` from ``scripts/host/Dockerfile.dev`` (Ubuntu 24.04, third_party/gem5/QEMU build dependencies, Rust, QEMU, ``qemu-img``)
   * - ``ghcr.io/third_party/gem5/gpu-fs:latest``
     - build image for guest GPU test programs; default of ``GPU_APP_BUILD_IMAGE`` for ``just build-gpu-tests`` and ``just build-gpu-app``
     - external image; override with ``GPU_APP_BUILD_IMAGE``
   * - Guest kernel and disk
     - ``build/rocm-local-installed/kernel`` and ``build/rocm-local-installed/disk``
     - ``just build-disk``: builds a raw bundle under ``build/rocm-local``, then installs it here

``ghcr.io/third_party/gem5/gpu-fs`` only builds guest GPU programs and is not the runtime image of a cosim session; the gem5 container started by the legacy shell launcher is ``cosim-dev:local``.

Guest image recipe
------------------

The repository contains exactly one guest image recipe, with the following identity and artifacts:

.. list-table::
   :header-rows: 1

   * - Item
     - Value
   * - Recipe identifier
     - ``ubuntu/24.04/x86_64/rocm/7.0``
   * - Role and architecture
     - ``vhost``, ``x86_64``
   * - Directory
     - ``resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/``
   * - Build entry points
     - ``build.sh``; template ``image.pkr.hcl``; provisioning ``provision.yml``
   * - Artifacts
     - ``vmlinux-rocm70`` kernel and the ``disk-image`` directory
   * - Guest disk
     - about 55 GB; the build needs about 60 GB of free space
   * - Build and check recipes
     - ``just build-disk``, ``just build-rocm-assets``, ``just check-rocm-image``, ``just check-rocm-syntax``, ``just test-rocm-assets``

Provenance and verification
---------------------------

Use these commands to record and check build provenance:

.. code-block:: bash

   git submodule status gem5 qemu ext/libvfio-user
   cat third_party/qemu/VERSION
   git -C gem5 describe --tags --always
   just ci-gem5-key
   just ci-rocm-assets key

- The gem5 cache key combines the project commit, gem5 commit, development image, build recipe and build arguments; see ``scripts/ci/runtime_artifact.py``.

- The guest image ``manifest.json`` records the recipe identifier, kernel release, image format and SHA-256 of kernel and disk; see ``scripts/host/cosim-image``.

- CI artifacts are named after the workflow run and retained for a fixed number of days; reuse across runs verifies the original provenance, see ``scripts/ci/image_artifact.py`` and ``scripts/ci/runtime_artifact.py``.

Sources and maintenance
-----------------------

Version information comes from these files; update this page when upgrading:

- ``third_party/qemu/VERSION`` and the repository gitlink: QEMU version.

- ``git submodule status gem5`` and ``justfile``: gem5 checkout and build target.

- ``Cargo.toml``: minimum Rust version.

- ``resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/recipe.toml``: guest OS and kernel.

- ``resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/provision.yml``, ``build.sh`` and ``image.pkr.hcl``: ROCm, PyTorch channel, ROM and build-tool versions.

Related pages
-------------

- Build artifact paths, session directories and source map (the artifact table lives there): :doc:`files_and_artifacts`

- Install and build flow: :ref:`gs-install`

- Environment and prerequisites: :ref:`gs-requirements`

- CI and artifact reuse: :ref:`contrib-ci`

- Commands and options: :ref:`launcher-cli`

- Known issues caused by version mismatch: :doc:`known_issues`

.. SPDX-License-Identifier: Apache-2.0

.. _gs-guest-image:

Guest image
===========

This page describes what the guest image contains, how to reuse a built
kernel and disk, and how to rebuild and verify it. A first run usually only
needs ``just build-disk``.

Image contents
--------------

.. list-table::
   :header-rows: 1

   * - Content
     - Detail
   * - Operating system
     - Ubuntu 24.04.2 LTS, x86_64
   * - Kernel
     - Linux 6.8.0-124-generic, paired with the exported disk
   * - GPU software stack
     - ROCm 7.0 and the amdgpu DKMS module; PyTorch from the rocm6.0 wheel channel
   * - GPU data
     - MI300X VBIOS ROM and IP discovery firmware
   * - Initialization
     - ``cosim-gpu-initialize.service`` writes the ROM and loads amdgpu at boot
   * - Login
     - Root serial autologin for scripts and interactive use
   * - Matching vHost
     - ``resources/vhosts/qemu.yaml`` declares kernel, root disk and cmdline

The image recipe and Ansible playbook are maintained in this repository at
``resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/``;
``recipe.toml`` records the Ubuntu and kernel versions, the Packer template
and the exported artifacts.

Reuse a prebuilt image
----------------------

.. code-block:: bash

   just build-disk        # build kernel and disk, install the local copies

``just build-disk`` creates raw artifacts under ``build/rocm-local`` and
installs the copies used by the standard samples here:

.. list-table::
   :header-rows: 1

   * - Artifact
     - Path
     - Approximate size
   * - Disk image
     - ``build/rocm-local-installed/disk``
     - 55 GB
   * - Kernel
     - ``build/rocm-local-installed/kernel``
     - 64 MB

``resources/vhosts/qemu.yaml`` points at these paths and uses
``modprobe.blacklist=amdgpu`` so the setup service loads the driver in the
right order.

Rebuild the image
-----------------

Packer boots a real QEMU/KVM virtual machine; Ansible installs packages and
configures ROCm; the builder then exports the disk and its matching kernel.
A rebuild needs:

- a Linux x86_64 host with accessible ``/dev/kvm``;
- at least 60 GiB free for construction and compression, plus memory for an
  8 GiB build virtual machine;
- QEMU, ``qemu-img``, Ansible, ``python3-tomli``, curl, unzip, Perl
  ``shasum`` and binutils;
- network access to Canonical, AMD, HashiCorp and PyTorch package servers.

.. code-block:: bash

   just build-rocm-assets build/rocm-custom    # reusable bundle
   just build-disk                             # local standard copies
   just test-rocm-assets build/rocm-custom     # reuse and corruption checks

``just build-rocm-assets`` builds one reusable kernel/disk bundle;
``just build-disk`` installs separate copies for the standard samples. The
recipes pin Packer and its plugin versions and verify the ISO and Packer
download checksums.

.. tip::

   If package downloads are slow, switch the build virtual machine to a
   reachable apt mirror and retry; completed outputs with matching inputs are
   verified and reused instead of rebuilt from scratch.

Bundle contents
---------------

A bundle directory contains the following files:

.. list-table::
   :header-rows: 1

   * - File
     - Purpose
   * - ``kernel``, ``disk``
     - Direct kernel boot and root disk; always used together
   * - ``manifest.json``
     - Source and input identities, build time, resolved versions and SHA-256
   * - ``kernel-release``, ``os-release``
     - Actual kernel and operating system versions
   * - ``image-packages.tsv``, ``python-packages.json``
     - Installed package inventories
   * - ``amdgpu-module.txt``, ``hipcc-version.txt``
     - Driver module and HIP compiler versions
   * - Build logs
     - Complete Packer and Ansible logs

Verify and reuse
----------------

- The manifest records input identities and resolved versions; completed
  outputs with matching inputs are verified and reused.
- Image integrity uses ``qemu-img check``; raw artifacts use paired file
  hashes and image information.
- The regression creates a fresh disk overlay for every workload so sessions
  cannot pollute each other.
- Checks: ``just check-rocm-image`` validates the complete configuration with
  real Packer plugins, and ``just check-rocm-syntax`` checks the template and
  playbook without building an image.
- The CI build, cache and reuse flow is documented in
  :ref:`CI and regressions <contrib-ci>`.

.. warning::

   The shipped image targets x86_64 only; AArch64 machines have no bootable
   guest image. Each machine independently selects its image in ``vhost``.

Related pages
-------------

- :doc:`install`
- :doc:`first_session`
- :doc:`verify_guest`
- :ref:`ref-vhost-image-recipe`
- :ref:`CI and regressions <contrib-ci>`

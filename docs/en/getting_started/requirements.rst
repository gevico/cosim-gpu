.. SPDX-License-Identifier: Apache-2.0

.. _gs-requirements:

Requirements
============

This page lists the host, tools, disk and memory needed to run the
co-simulation and gives a one-shot self-check. Component versions live in
the :ref:`version matrix <ref-version-matrix>` and are not repeated here.

Host environments
-----------------

- Standard path: a Linux x86_64 host with accessible ``/dev/kvm``. The
  shipped guest image targets x86_64 and booting it needs KVM.
- Without KVM you can still build the components, run ``cosim validate``,
  ``cosim run <topology.yaml> --dry-run`` and ``cosim graph``, and run paused
  TCG host-only sessions; those sessions do not boot a guest.
- Linux aarch64 hosts support builds and planning; the shipped guest image
  is not an AArch64 build.
- macOS and Windows use the development container for builds, planning and
  TCG sessions; a bootable guest needs a Linux host with KVM, see
  :doc:`platforms/container`.
- The build recipes do not provide a RISC-V host profile.

Tools and versions
------------------

.. list-table::
   :header-rows: 1

   * - Requirement
     - Detail
   * - Host OS
     - Linux x86_64 with KVM; macOS and Windows go through the container
   * - Rust and Cargo
     - 1.95 or newer, used to build the ``cosim`` launcher
   * - just
     - 1.46 or newer; every task is a recipe in the ``justfile``
   * - Docker
     - Daemon running and the current user in the ``docker`` group
   * - KVM
     - ``/dev/kvm`` exists and is readable and writable
   * - QEMU
     - Built from the ``qemu`` submodule; samples point at ``build/qemu/qemu-system-x86_64``
   * - Disk tools
     - ``build/qemu/qemu-img`` from the same QEMU build, for image checks, creation and session overlays
   * - Other tools
     - ``git``, ``screen``, ``unzip``; image builds also need Packer and Ansible

Disk and memory
---------------

.. list-table::
   :header-rows: 1

   * - Resource
     - Minimum
     - Recommended
   * - Disk
     - 120 GB free (about 55 GB image plus build artifacts)
     - 150 GB or more
   * - Memory
     - 16 GB
     - 32 GB or more, especially for gem5 linking and 8-GPU machines
   * - Shared-memory filesystem
     - Holds the complete memory pool of the selected machine
     - About 24 GiB for the standard ``single-gpu`` session

Checklist
---------

.. code-block:: bash

   just --list                 # task entry point
   ls -l /dev/kvm              # KVM exists and is accessible
   docker info >/dev/null      # development and gem5 containers
   df -h .                     # disk space
   free -h                     # memory

If a check fails, read the dependency and permission notes in
:doc:`platforms/linux`, or use :doc:`platforms/container` to keep building
and planning.

Related pages
-------------

- :doc:`install`
- :doc:`platforms/linux`
- :doc:`platforms/container`
- :ref:`Version matrix <ref-version-matrix>`

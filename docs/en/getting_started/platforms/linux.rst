.. SPDX-License-Identifier: Apache-2.0

.. _gs-platform-linux:

Linux host
==========

This page covers native Linux builds and runs: dependencies, KVM
permissions and distribution differences. See :doc:`container` when using
the development container.

When to use it
--------------

Run natively when the host meets these conditions; it is the fastest path
and the easiest to debug with real hardware:

- Linux x86_64 with ``/dev/kvm`` readable and writable by the current user;
- the gem5, QEMU and Rust build dependencies listed in
  ``scripts/host/Dockerfile.dev`` are installed;
- the Docker daemon works (the development container and GPU application
  builds use it);
- disk and memory meet the minimums in :doc:`../requirements`.

If build dependencies are missing or the distribution differs, move only the
builds into the development container, see :doc:`container`.

System dependencies
-------------------

The complete package list is in ``scripts/host/Dockerfile.dev``; it falls into
these groups:

.. list-table::
   :header-rows: 1

   * - Group
     - Typical packages
     - Purpose
   * - C/C++ toolchain
     - ``build-essential``, ``cmake``, ``m4``, ``ninja-build``
     - Build QEMU and gem5
   * - gem5 dependencies
     - ``scons``, ``python3-dev``, ``libboost-all-dev``, ``libprotobuf-dev``
     - gem5 builds and Python scripts
   * - QEMU dependencies
     - ``libglib2.0-dev``, ``libpixman-1-dev``, ``libslirp-dev``, ``libjson-c-dev``
     - QEMU softmmu and the vfio-user backend
   * - Test dependencies
     - ``libcmocka-dev``, ``python3-venv``
     - QEMU unit tests and Python virtual environments
   * - Image build
     - ``ansible-core``, ``python3-tomli``, ``unzip``
     - Packer/Ansible guest image builds
   * - Rust
     - Rust 1.95 or newer and Cargo
     - Build the ``cosim`` launcher

The gem5 binary links against Ubuntu 24.04 libraries, so build it in a
compatible environment; use the development container on distributions that
differ significantly.

KVM and permissions
-------------------

.. code-block:: bash

   ls -l /dev/kvm
   test -r /dev/kvm && test -w /dev/kvm && echo kvm-ok

``/dev/kvm`` is usually owned by ``root:kvm`` with mode ``0660``. Add the
current user to the ``kvm`` group and log in again:

.. code-block:: bash

   sudo usermod -aG kvm "$USER"

Docker must also be accessible: the user is in the ``docker`` group and the
daemon is running.

WSL2 and nested virtualization
------------------------------

- WSL2 needs nested virtualization enabled and ``/dev/kvm`` visible inside
  the distribution;
- keep sources and build outputs on an ext4 filesystem, not on ``/mnt/c``;
- allocate memory and CPUs at least at the minimums in
  :doc:`../requirements`, especially for gem5 linking;
- the container path also needs ``/dev/kvm`` passed through to the container.

Verify the environment
----------------------

.. code-block:: bash

   git submodule status
   just --list
   docker info >/dev/null && echo docker-ok
   ls -l /dev/kvm
   build/qemu/qemu-img --version

Once these checks pass, build with :doc:`../install` and start
:doc:`../first_session`.

Related pages
-------------

- :doc:`../requirements`
- :doc:`../install`
- :doc:`container`
- :ref:`Version matrix <ref-version-matrix>`

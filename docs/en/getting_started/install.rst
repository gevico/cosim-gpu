.. SPDX-License-Identifier: Apache-2.0

.. _gs-install:

Install and build
=================

This page gives the default commands to fetch the sources, initialize the
submodules and build QEMU, gem5, the guest assets and the Rust launcher.
Host dependencies and container differences are covered in
:doc:`platforms/linux` and :doc:`platforms/container`.

Sources and submodules
----------------------

.. code-block:: bash

   git clone https://github.com/gevico/cosim-gpu.git
   cd cosim-gpu
   just dev-submodules

``just dev-submodules`` initializes the ``qemu``, ``gem5`` and
``gem5-resources`` submodules. QEMU and gem5 come from their submodules; the
co-simulation does not patch either of them.

Choose the build environment
----------------------------

Build recipes run through ``scripts/host/dev.sh`` on the host or in a temporary
development container, selected by ``COSIM_ENV``: Linux defaults to
``host`` and other systems default to ``container``.

.. code-block:: bash

   just dev-image                  # once, on non-Linux hosts or missing deps
   export COSIM_ENV=container      # run the following builds in the container

Container contents, mounts and limits are described in
:doc:`platforms/container`.

Build everything
----------------

.. code-block:: bash

   just build-all

``just build-all`` runs the following recipes in order:

.. list-table::
   :header-rows: 1

   * - Recipe
     - Output
   * - ``just build-qemu``
     - ``build/qemu/qemu-system-x86_64`` with ``vfio-user-pci`` and KVM support
   * - ``just build-gem5``
     - ``build/gem5/<arch>/VEGA_X86/gem5.opt``
   * - ``just build-disk``
     - ``build/rocm-local-installed/{disk,kernel}``
   * - ``just build-gpu-app``
     - ``build/apps/square/square.default``
   * - ``just build-cosim``
     - The Rust ``cosim`` launcher

The guest image build uses QEMU, and the GPU application build runs in its own
GPU container.

Build in steps
--------------

The first build takes a long time, so components can be retried:

.. code-block:: bash

   just build-qemu                 # all host CPUs
   just build-qemu 4               # limit the number of jobs
   just build-gem5                 # all host CPUs
   just build-gem5 1               # limit parallelism when linking OOMs
   just build-disk                 # needs /dev/kvm, QEMU and about 60 GB
   just build-cosim

``just build-gem5`` defaults to the number of CPU cores; reduce it to 1 when
the linker is OOM-killed.

Guest assets
------------

``just build-disk`` produces a matching kernel and disk that must be used
together. Image contents, the build flow, the bundle and verification are
described in :doc:`guest_image`.

Verify the build
----------------

.. code-block:: bash

   just run-cli validate resources/machines/single-gpu.yaml \

   ls -l build/qemu/qemu-system-x86_64
   ls -l build/gem5/*/VEGA_X86/gem5.opt
   ls -l build/rocm-local-installed/disk build/rocm-local-installed/kernel

``validate`` only checks the topology and vHost; add ``--assets`` to also
check the local input files.

Related pages
-------------

- :doc:`guest_image`
- :doc:`first_session`
- :doc:`platforms/linux`
- :doc:`platforms/container`
- :ref:`Files, artifacts and source map <ref-files-and-artifacts>`

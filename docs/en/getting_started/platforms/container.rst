.. SPDX-License-Identifier: Apache-2.0

.. _gs-platform-container:

Development container
=====================

This page describes the build environment the development container
provides, how ``scripts/host/dev.sh`` behaves, and the limits when building,
planning and running sessions inside it. Native Linux is covered in
:doc:`linux`.

When to use it
--------------

- macOS and Windows use the development container by default for builds,
  ``plan``/``graph`` and TCG sessions; a bootable KVM guest still needs a
  Linux host.
- On Linux hosts missing gem5, QEMU or Rust build dependencies, move only
  the builds into the container and keep runs on the host.
- Use the container when a build environment identical to CI is wanted.

Build and select the environment
--------------------------------

.. code-block:: bash

   just dev-image                  # build the cosim-dev:local image
   export COSIM_ENV=container      # explicitly select the container

``just dev-image`` builds ``cosim-dev:local`` from
``scripts/host/Dockerfile.dev``: Ubuntu 24.04 with gem5 and QEMU build
dependencies, the Rust toolchain, QEMU and ``qemu-img``. When ``COSIM_ENV``
is unset, Linux uses ``host`` and other systems use ``container``.

How dev.sh behaves
------------------

Build, topology and Rust check recipes run through ``scripts/host/dev.sh``:

.. list-table::
   :header-rows: 1

   * - Aspect
     - Behavior
   * - Mounts
     - The source tree is mounted at its host absolute path, so paths in YAML, plans and logs match
   * - User
     - Runs with the current uid/gid, so artifacts keep their host ownership
   * - Lifetime
     - ``docker run --rm --init``; the container is removed when the command exits
   * - KVM
     - ``/dev/kvm`` is passed through when the host provides it
   * - Shared memory
     - The container has its own ``/dev/shm`` sized to the Docker daemon memory
   * - Cache
     - Cargo cache and outputs are written under ``build/`` in the repository
   * - Disk locks
     - The ``COSIM_DISK_LOCK_DIR`` directory is mounted for image leases
   * - Stdin lifeline
     - Sets ``COSIM_STDIN_LIFELINE=1`` so the session ends when the client exits

Files outside the source tree are not visible in the container; mount them
explicitly with ``--mount`` when needed.

Working inside the container
----------------------------

.. code-block:: bash

   just dev-shell                                  # one-off interactive shell
   COSIM_ENV=container just build-cosim            # build the launcher in the container
   just run-topology resources/machines/single-gpu.yaml --dry-run
   just run-topology resources/machines/host-only.yaml --run-for 1

``just run-topology`` and ``just run-cli`` themselves also use ``dev.sh``;
with ``COSIM_ENV=container``, ``cosim run`` executes inside the container.
Host-only and TCG sessions do not need KVM and can run there.

Limitations
-----------

- Without ``/dev/kvm`` a bootable guest cannot start; only builds, planning
  and TCG sessions are possible.
- The container's ``/dev/shm`` disappears with the container, so sessions
  cannot persist across containers.
- Session directories live in the mounted source tree, so logs and verdicts
  remain on the host.
- Nested filesystems and Docker networking add overhead; long simulations are
  better on a native Linux host.

.. note::

   The development container is for development and checks. Guest image
   builds need real ``/dev/kvm`` and QEMU and usually run directly on a Linux
   host.

Related pages
-------------

- :doc:`../requirements`
- :doc:`../install`
- :doc:`linux`
- :ref:`Cosim Launcher <launcher-index>`

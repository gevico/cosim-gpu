.. SPDX-License-Identifier: Apache-2.0

.. _ref-legacy-launcher:

Legacy launcher flags
=====================

This page is the single source of truth for the shell launcher ``scripts/host/cosim_launch.sh`` and the gem5 cosim configuration options. Values follow the current script and ``mi300_cosim.py`` and correct the stale defaults found in older documentation.

Scope
-----

``scripts/host/cosim_launch.sh`` is invoked through ``just run-launch`` and starts one guest and one gem5 container connected over vfio-user; ``just test-gpu`` and ``scripts/host/run_cosim_tests.sh`` use the same path. The current documented main path is the YAML launcher, and the two must not share options: the tables below describe the shell launcher and the gem5 configuration it calls.

Shell launcher options
----------------------

The defaults below are the effective values in the script. The ``--socket-path`` help text shows ``/tmp/gem5-mi300x.sock``, but the script always appends the run identifier, so the effective default carries a ``-<run-id>`` suffix.

.. list-table::
   :header-rows: 1

   * - Option
     - Effective default
     - Notes
   * - ``--disk-image PATH``
     - ``build/rocm-local-installed/disk``
     - guest disk image
   * - ``--kernel PATH``
     - ``build/rocm-local-installed/kernel``
     - guest vmlinux
   * - ``--qemu-bin PATH``
     - ``build/qemu/qemu-system-x86_64``, otherwise ``qemu-system-x86_64`` from ``PATH``
     - QEMU binary
   * - ``--gem5-bin PATH``
     - ``build/gem5/<arch>/VEGA_X86/gem5.opt``
     - gem5 binary
   * - ``--gem5-docker IMAGE``
     - ``cosim-dev:local``
     - container image that runs gem5
   * - ``--socket-path PATH``
     - ``/tmp/gem5-mi300x-<run-id>.sock``
     - vfio-user socket; multi-GPU derives ``<stem>-<n>.sock``
   * - ``--host-mem SIZE``
     - ``8G``
     - guest RAM
   * - ``--host-cpus N``
     - ``4``
     - guest vCPU count
   * - ``--vram-size SIZE``
     - ``16GiB``
     - GPU VRAM size
   * - ``--num-cus N``
     - ``40``
     - GPU compute unit count
   * - ``--gem5-debug FLAGS``
     - none
     - passed to gem5 as ``--debug-flags``
   * - ``--qemu-trace EVENTS``
     - none
     - QEMU trace events
   * - ``--share-dir PATH``
     - none
     - directory shared with the guest over 9p under mount tag ``cosim_share``
   * - ``--num-gpus N``
     - ``1``
     - GPU instance count; multiple GPUs use in-process multi-GPU mode
   * - ``--timeout SECS``
     - ``120``
     - gem5 initialization timeout
   * - ``--force-clean``
     - off
     - list orphaned cosim resources (dry run)
   * - ``--confirm``
     - off
     - delete orphaned resources together with ``--force-clean``
   * - ``-h`` / ``--help``
     - —
     - print help

Derived paths and names
-----------------------

The run identifier combines a timestamp and four random bytes; every path below derives from it:

.. list-table::
   :header-rows: 1

   * - Path or name
     - Meaning
     - Notes
   * - ``<YYYYmmdd-HHMMSS>-<8 hex>``
     - run identifier (``COSIM_RUN_ID``)
     - source of every derived path
   * - ``gem5-cosim-<run-id>``
     - gem5 container name
     - used by ``docker logs`` and ``docker exec``
   * - ``/tmp/cosim-<run-id>.session``
     - session directory and ``resources.manifest``
     - cleanup and diagnostics
   * - ``/tmp/cosim-<run-id>.log``
     - screen log of the QEMU console
     - copied into diagnostics on failure
   * - ``/dev/shm/cosim-guest-ram-<run-id>``
     - guest RAM shared memory file
     - created and removed by the launcher
   * - ``/dev/shm/mi300x-vram-<run-id>``
     - single-GPU VRAM shared memory file
     - created and removed by the launcher
   * - ``/dev/shm/mi300x-vram-<run-id>-<n>``
     - per-GPU VRAM shared memory file for multiple GPUs
     - used when ``--num-gpus`` is greater than 1
   * - ``artifacts/standalone/<run-id>/``
     - diagnostic artifact directory captured on failure
     - contains gem5 logs, container inspect output, console log and related files

gem5 config options
-------------------

``third_party/gem5/configs/example/gpufs/mi300_cosim.py`` also accepts its own option set; the YAML device adapter uses only a subset (see :doc:`device_adapters`). The table lists the complete defaults of the configuration script.

.. list-table::
   :header-rows: 1

   * - Option
     - Default
     - Notes
   * - ``--socket-path``
     - ``/tmp/gem5-mi300x.sock``
     - single-GPU vfio-user socket; base path for multiple GPUs
   * - ``--shmem-path``
     - ``/mi300x-vram``
     - POSIX shared memory name for VRAM; base name for multiple GPUs
   * - ``--shmem-host-path``
     - ``/cosim-guest-ram``
     - POSIX shared memory name for guest RAM
   * - ``--dgpu-mem-size``
     - ``16GiB``
     - VRAM size
   * - ``--mem-size``
     - ``8GiB``
     - guest RAM size
   * - ``--num-compute-units``
     - ``40``
     - compute unit count
   * - ``--num-gpus``
     - ``1``
     - GPU instances inside one process
   * - ``--shared-pool``
     - ""
     - existing pool file used by the YAML launcher; when set it overrides the shared-memory options
   * - ``--pool-vram-offset``
     - ``0``
     - VRAM byte offset in the pool file
   * - ``--host-memory-ranges``
     - none
     - guest RAM range JSON passed by the YAML launcher
   * - ``--xgmi-topology``
     - none
     - ``mesh`` or ``ring``; requires ``--num-gpus`` of at least 2
   * - ``--xgmi-bandwidth``
     - ``128GB/s``
     - xGMI per-link bandwidth
   * - ``--xgmi-latency``
     - ``100ns``
     - xGMI per-hop latency

The in-process multi-GPU mode is exposed only by this configuration script and the shell launcher; the YAML adapter hard-codes ``--num-gpus=1``.

Differences from the YAML launcher
----------------------------------

.. list-table::
   :header-rows: 1

   * - Capability
     - Shell launcher
     - YAML launcher
   * - Launch unit
     - one guest and one gem5 container (1 to N GPUs)
     - one topology document with any number of machines
   * - Launch command
     - ``just run-launch``
     - ``just run-topology``
   * - Input
     - command-line options plus fixed disk and kernel paths
     - one topology YAML containing each machine's vHost
   * - Multiple GPUs
     - ``--num-gpus N``, multiple GPUs inside one gem5 process
     - one device process per GPU
   * - gem5 debug flags
     - ``--gem5-debug FLAGS``
     - device ``args.gem5_debug_flags``
   * - QEMU trace
     - ``--qemu-trace EVENTS``
     - no matching field; append QEMU arguments through host ``args``
   * - Host directory sharing
     - ``--share-dir PATH`` (9p)
     - no built-in field; add it through host ``args``
   * - SSH access
     - port forward to 2222, guest console auto-login
     - determined by the image and host configuration
   * - Failure classification and diagnostics
     - session directory, screen log and ``artifacts/standalone/<run-id>/``
     - ``verdict.json`` and the ``[COSIM_VERDICT]`` line

Sources and maintenance
-----------------------

Sources of the option definitions:

- ``scripts/host/cosim_launch.sh``: option parsing, defaults, derived paths and container startup.

- ``scripts/host/cosim_lib.sh``: run identifier, container name, socket, shared memory, session directory and diagnostic artifact paths.

- ``third_party/gem5/configs/example/gpufs/mi300_cosim.py``: gem5-side options and defaults.

- ``justfile``: ``run-launch`` and ``test-gpu`` entry points.

Verify the help text and effective defaults with:

.. code-block:: bash

   scripts/host/cosim_launch.sh --help
   just run-launch --force-clean

Related pages
-------------

- Legacy launcher workflow: :ref:`launcher-legacy`

- Versions, images and provenance: :doc:`version_matrix`

- Files and session paths: :doc:`files_and_artifacts`

- Guest parameters: :doc:`guest_parameters`

- Related known issues: :doc:`known_issues`

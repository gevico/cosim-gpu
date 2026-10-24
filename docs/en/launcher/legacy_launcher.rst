.. SPDX-License-Identifier: Apache-2.0

.. _launcher-legacy:

Legacy shell launcher
======================

This page describes the legacy shell startup path: its position, its flow and how it differs from the Rust launcher. New work should use the Rust launcher; this page exists for maintenance and manual debugging.

Position
---------

``scripts/host/cosim_launch.sh`` is an early one-command startup script exposed as the ``just run-launch`` recipe. It targets a single guest: gem5 runs only the GPU model inside a Docker container, QEMU runs the guest on the host with KVM, and the two communicate over a Unix socket using the standard vfio-user protocol.

- gem5 uses the ``cosim-dev:local`` image with ``build/gem5/<native>/VEGA_X86/gem5.opt`` as the default binary and ``third_party/gem5/configs/example/gpufs/mi300_cosim.py`` as the configuration.
- QEMU prefers ``build/qemu/qemu-system-x86_64`` and falls back to a system QEMU found in ``PATH``.
- Each run generates a ``COSIM_RUN_ID`` used in socket, shared memory and screen log names to reduce collisions between concurrent runs.
- The guest kernel and disk default to ``build/rocm-local-installed/kernel`` and ``disk``.

Differences from the Rust Launcher
-----------------------------------

.. list-table::
   :header-rows: 1

   * - Aspect
     - Rust launcher
     - Legacy shell launcher
   * - Input
     - YAML topology and vHost documents
     - Command-line options and fixed build artifact paths
   * - Device model
     - Adapter selection, one GPU per process
     - ``mi300_cosim.py``, where ``--num-gpus`` enables multiple GPUs in one process
   * - Process management
     - Readiness probes, leases, signal escalation and a verdict
     - Shell, screen, Docker and manual cleanup
   * - Records
     - Structured files under ``.cosim/<name>``
     - Session files and screen logs under ``/tmp`` with the run id
   * - Position
     - Default path for development and CI
     - Manual debugging and compatibility with old scripts

Run Flow
---------

1. Prepare build artifacts with ``just dev-image``, ``just build-qemu`` and ``just build-gem5``.
2. Generate a run id and derive the socket, the ``/dev/shm`` shared memory names, the screen session and the log path from it.
3. Start the gem5 container and wait for the vfio-user socket.
4. Start QEMU on the host with the kernel and disk, attaching the GPU as a vfio-user client.
5. Watch the guest serial console in the screen session; ``cosim-gpu-initialize.service`` writes the ROM and loads the driver inside the guest.
6. End the run and clean up the container, socket, shared memory and screen session. Leftovers can be listed with ``just run-preflight`` and removed with ``just run-clean-orphans``.

Common Commands
----------------

.. code-block:: bash

   # Start with the default options
   just run-launch
   # Enable gem5 debug flags
   just run-launch --gem5-debug MI300XCosim
   # Start two GPU instances in one gem5 process
   just run-launch --num-gpus 2
   # Show all options
   ./scripts/host/cosim_launch.sh --help
   # Inspect and remove leftover sockets, shared memory and containers
   just run-preflight
   just run-clean-orphans

Maintenance Boundaries
-----------------------

- The canonical option table is :ref:`ref-legacy-launcher`; this page does not duplicate defaults or per-option descriptions.
- New topologies, devices and automated tests belong in the Rust launcher; this script is maintained for compatibility only.
- Options of ``mi300_cosim.py`` such as ``--num-gpus``, ``--xgmi-topology`` and ``--shmem-path`` belong to the gem5 configuration, not to the YAML adapter contract.

Sources
--------

- Launcher scripts: ``scripts/host/cosim_launch.sh`` and ``scripts/host/cosim_lib.sh``.
- Preflight script: ``scripts/host/cosim_preflight.sh``.
- gem5 configuration: ``third_party/gem5/configs/example/gpufs/mi300_cosim.py``.
- just recipes: ``run-launch``, ``run-preflight`` and ``run-clean-orphans`` in ``justfile``.

Related Pages
--------------

- :doc:`index` for an overview of the Rust launcher.
- :doc:`cli` for Rust launcher commands and options.
- :ref:`ref-legacy-launcher` for the canonical legacy option reference.

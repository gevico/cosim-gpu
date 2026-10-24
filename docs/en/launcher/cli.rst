.. SPDX-License-Identifier: Apache-2.0

.. _launcher-cli:

CLI
====

This page is the quick reference for the ``cosim`` commands: subcommands, common options, output and exit codes.

Global Options
---------------

``--resources`` is the only global option. It defaults to ``resources/`` and resolves imports that are not relative to the importing file. Resource paths are relative to the workspace root, and executable names without a ``/`` are searched in ``PATH`` while planning.

Subcommands
------------

.. list-table::
   :header-rows: 1

   * - Command
     - Main arguments
     - Output and effect
   * - ``validate``
     - topology, ``--assets``
     - Validates documents, identifiers and memory layouts; ``--assets`` also checks local input files. Prints the machine and device counts on success.
   * - ``graph``
     - topology
     - Prints machines and device connections as a Mermaid flowchart.
   * - ``schema``
     - none
     - Prints the JSON Schema of topology documents.
   * - ``run``
     - topology, directory and run options
     - Starts and supervises the session, printing event lines and the final verdict.
   * - ``clean``
     - run directory
     - Removes the session resources listed in ``manifest.json`` and keeps the logs.

Run Options
------------

.. list-table::
   :header-rows: 1

   * - Option
     - Default
     - Description
   * - ``--dry-run``
     - off
     - Resolves image recipes and prints the launch plan without building images or starting processes.
   * - ``--run-dir``
     - ``.cosim/<12 random characters>``
     - New session directory; dry-run defaults to ``.cosim/dry-run``.
   * - ``--pool-dir``
     - ``/dev/shm/cosim-<name>-<hash>`` on Linux, ``<run-dir>/memory`` elsewhere
     - Shared memory pool directory.
   * - ``--ready-timeout``
     - ``120``
     - Seconds each process has to pass every readiness probe after it starts.
   * - ``--run-for``
     - none
     - Seconds to run after every process is ready; the session ends when it elapses.
   * - ``--qemu-img``
     - ``qemu-img``
     - Tool used to create missing images and overlays.
   * - ``--stdin-lifeline``
     - environment variable ``COSIM_STDIN_LIFELINE``
     - Ends the session when standard input closes; the development container sets it.

Typical Workflows
------------------

.. code-block:: bash

   # Build the launcher once
   just build-cosim
   # Validate documents, identifiers and local input files only
   just run-cli validate resources/machines/gpu-8.yaml  --assets
   # Inspect the resolved plan
   just run-topology resources/machines/mixed-models.yaml --dry-run
   # Inspect machine and device connections
   just run-cli graph resources/clusters/cluster-4x8.yaml
   # Print the JSON Schema of topology documents
   just run-cli schema
   # Run and supervise a session
   just run-topology resources/machines/single-gpu.yaml
   # Remove resources left by an abnormal exit
   just run-cli clean .cosim/<name>

``just run-cli`` passes its arguments through to ``cosim``. ``just run-topology`` runs in the development container with the repository root as the workspace.

Events, Exit Codes and the Verdict
-----------------------------------

- The session prints ``started``, ``ready``, ``exited`` and ``stopped`` event lines while it runs.
- The first SIGINT or SIGTERM requests graceful shutdown; later signals skip the remaining grace periods.
- Exit code: 0 when the verdict is ``PASS``, 1 otherwise; command-line and loading errors also return 1.
- The last line is ``[COSIM_VERDICT]`` followed by JSON, which is also written to ``verdict.json`` in the run directory.

.. code-block:: text

   [COSIM_VERDICT] {"status":"PASS","reason":null,"cleanup_errors":[],"users_stopped":true}

Sources
--------

- Command and option definitions: ``crates/cosim-cli/src/main.rs``.
- ``Verdict`` and ``Status``: ``crates/cosim-runtime/src/session.rs``.
- Plan structure: ``crates/cosim-runtime/src/plan.rs``.
- Sample topologies and vHost: ``resources/machines/`` and ``resources/vhosts/qemu.yaml``.

Related Pages
--------------

- :doc:`yaml_pipeline` explains how input documents become a plan.
- :doc:`session_lifecycle` explains what happens after ``run`` starts.
- :doc:`debugging_sessions` covers reading logs and verdicts.
- :ref:`ref-files-and-artifacts` lists session directories and build artifacts.

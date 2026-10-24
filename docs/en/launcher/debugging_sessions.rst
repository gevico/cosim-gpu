.. SPDX-License-Identifier: Apache-2.0

.. _launcher-debugging-sessions:

Debugging sessions
===================

This page explains how to read session events, logs and verdicts, how to identify the first failing component from common startup failures, and how to safely recover resources left by an abnormal exit.

Session Events and Logs
------------------------

- ``run`` prints ``session: <run-dir>`` when it starts, then prints ``started``, ``ready``, ``exited`` and ``stopped`` event lines.
- Each process writes combined standard output and standard error to ``output.log`` in its work directory; gem5 also writes its ``m5out/`` directory there.
- vHost serial output goes to ``<machine>/vhost/serial.log`` and is also available through the serial socket.
- ``verdict.json`` records the final result; the same content is printed on the ``[COSIM_VERDICT]`` line.

.. code-block:: bash

   # The run directory is printed on the session line; it defaults under .cosim/
   ls .cosim/<name>
   # Tail the process logs
   tail -n 50 .cosim/<name>/m0/mi300x-0/output.log
   tail -n 50 .cosim/<name>/m0/vhost/output.log
   tail -n 50 .cosim/<name>/m0/vhost/serial.log
   cat .cosim/<name>/verdict.json

Reading the Verdict
--------------------

.. list-table::
   :header-rows: 1

   * - Field
     - Meaning
   * - ``status``
     - ``PASS`` or ``FAIL``.
   * - ``reason``
     - The first failure, or ``null`` when there was none.
   * - ``cleanup_errors``
     - Failures while releasing session resources.
   * - ``users_stopped``
     - Whether every owned process is known to have exited; when ``false``, resources are kept for inspection.

.. code-block:: json

   {
     "status": "FAIL",
     "reason": "host m0 exited with status 1",
     "cleanup_errors": [],
     "users_stopped": true
   }

Common Startup Failures
------------------------

.. list-table::
   :header-rows: 1

   * - Symptom
     - First check
     - Action
   * - Unknown field or unknown template while loading
     - YAML field names, template names and ``use`` references
     - Fix the document against ``cosim schema``.
   * - An import is missing
     - Whether the path is relative to the importing file or to ``--resources``
     - Fix the relative path or pass the correct ``--resources`` directory.
   * - A program cannot be found
     - ``runtime.binary`` and ``PATH``
     - Use a workspace-relative path or build the binary first.
   * - A device readiness probe times out
     - The readiness marker and socket in the device ``output.log``
     - Check that the binary runs, that ``ready_log`` is correct and that the socket is not taken.
   * - The vHost readiness probe times out
     - The ``serial.wait_for`` marker and ``serial.timeout``
     - Check the guest command line and the serial configuration.
   * - Pool capacity is exhausted
     - Free space on the pool filesystem and concurrent sessions
     - Free space or clean other sessions and retry.
   * - Remote placement is rejected
     - ``placement.agent``
     - ``cosim run`` executes locally only; remove the remote placement.
   * - ``clean`` refuses to run
     - Whether the launcher or a child is still alive and holds ``session.lock``
     - Stop the related processes, then run ``clean``.

Cleanup and Leftover Resources
-------------------------------

- On a normal exit the launcher has removed sockets, overlays, pools and the pool directory, keeping only logs and metadata.
- After the launcher was killed or exited abnormally, use ``cosim clean <run-dir>`` to remove the resources listed in ``manifest.json``.
- ``clean`` removes pool contents only from a pool directory whose ownership marker names this session, so it does not touch other sessions.
- If ``clean`` cannot run, first check whether ``session.lock`` is still held by a process, then inspect the resource paths in ``manifest.json``.

Sources
--------

- Events and the verdict: ``crates/cosim-runtime/src/session.rs``.
- Readiness probes: ``crates/cosim-runtime/src/probe.rs``.
- Cleanup: ``crates/cosim-runtime/src/manifest.rs``.
- Session file names: ``crates/cosim-runtime/src/layout.rs``.

Related Pages
--------------

- :doc:`session_lifecycle` for session rules and resources.
- :doc:`cli` for commands, options and exit codes.
- :ref:`ref-known-issues` for the complete symptom/cause/fix list.
- :ref:`sim-debugging-models` for debugging on the gem5 model side.

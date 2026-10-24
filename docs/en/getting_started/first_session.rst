.. SPDX-License-Identifier: Apache-2.0

.. _gs-first-session:

First session
=============

This page starts the first co-simulation session with the ``single-gpu``
machine whose vHost selects ``ubuntu/24.04/x86_64/rocm/7.0``, connects to the guest console
and shuts the session down cleanly.

Prerequisites
-------------

- The steps in :doc:`install` have run and
  ``build/rocm-local-installed/disk`` plus
  ``build/rocm-local-installed/kernel`` exist;
- ``/dev/kvm`` is accessible on the Linux host;
- the guest assets are ready, see :doc:`guest_image`;
- the host has room for the session memory pool (about 24 GiB for the
  standard ``single-gpu`` machine).

Launch the session
------------------

.. code-block:: bash

   just run-topology resources/machines/single-gpu.yaml \


The recipe calls the Rust ``cosim`` launcher, loads the topology and vHost,
checks the local input files, and starts the processes in the order described
in :doc:`../architecture/execution_flow`. The launcher prints the session
directory first, for example ``session: .cosim/1f0c3a4b5c6d``.

What the session does
---------------------

1. Parse and validate the YAML: resolve imports and device templates and
   expand the machine list.
2. Combine the local page size, ``PATH`` and disk lock directory into an
   execution plan.
3. Create the session directory and write its manifest, plan and options.
4. Create the shared memory pool, reserve capacity and prepare a qcow2
   overlay for the root disk.
5. Start the gem5 MI300X device process and wait for its vfio-user socket
   and listening marker.
6. Start the host QEMU, complete the QMP handshake and boot the guest from
   the direct kernel.
7. After boot, ``cosim-gpu-initialize.service`` finishes GPU initialization in about 40 s.

.. note::

   Device processes start before the host and stop after it. The session ends
   when the vHost exits with status 0. Each process has 120 seconds to become
   ready by default; use ``--ready-timeout`` to change it.

Connect to the guest console
----------------------------

The host exposes the serial port as a Unix socket and also writes a log
file. Connect with any Unix socket client, for example:

.. code-block:: bash

   socat -,raw,echo=0 unix-connect:.cosim/<session>/m0/serial.sock

Without ``socat``, use ``nc -U .cosim/<session>/m0/serial.sock``. To only
watch the output, follow the log:

.. code-block:: bash

   tail -f .cosim/<session>/m0/vhost/serial.log

The guest logs in as root on the serial port, so commands can be run
directly. After the first login, check the GPU as described in
:doc:`verify_guest`.

Session artifacts
-----------------

The run directory defaults to ``.cosim/<random name>``; use ``--run-dir``
to pin it:

.. list-table::
   :header-rows: 1

   * - Path
     - Content
   * - ``plan.json``, ``options.json``
     - Resolved execution plan and run options
   * - ``manifest.json``, ``verdict.json``
     - Session resource inventory and final verdict
   * - ``m0/layout.json``
     - Memory pool regions for the machine
   * - ``m0/serial.sock``, ``m0/vhost/serial.log``
     - Guest serial socket and log
   * - ``m0/vhost/output.log``, ``m0/mi300x-0/output.log``
     - Output logs of the host and device processes

Shut down the session
---------------------

- Run ``poweroff`` inside the guest OS; the session ends after the vHost exits
  cleanly.
- Or press Ctrl-C once in the launcher terminal to start an ordered
  shutdown: stop the host, then the devices, then delete sockets, overlays
  and the memory pool.
- The launcher prints a final ``[COSIM_VERDICT]`` line with the status and
  cleanup results.
- After the launcher is killed, run ``just run-cli clean .cosim/<session>``
  to remove leftover resources; logs are kept.

.. tip::

   Use ``--run-for 60`` only for timed runs; the session ends after all
   processes are ready and the timer expires. The development container
   sets a standard-input lifeline, so the session ends when its client exits.

Related pages
-------------

- :doc:`verify_guest`
- :doc:`guest_image`
- :ref:`Execution flow <arch-execution-flow>`
- :ref:`Session lifecycle and resources <launcher-session-lifecycle>`
- :ref:`Debugging sessions <launcher-debugging-sessions>`

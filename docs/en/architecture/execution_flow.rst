.. SPDX-License-Identifier: Apache-2.0

.. _arch-execution-flow:

Execution flow
==============

A session starts from a YAML topology, then goes through planning, resource
preparation, process startup, readiness probes, shutdown and a final verdict.
This page follows that order.

From topology to plan
---------------------

The launcher first loads and validates the topology:

- parse ``imports``, ``templates``, ``kinds`` and ``machines``, expand
  ``count`` and check identifiers, references and the device limit;
- validate each machine's vHost, including its image, direct-boot fields and
  disks;
- combine local facts into the plan: page size, absolute ``PATH`` and the disk
  lock directory (``COSIM_DISK_LOCK_DIR``, default
  ``~/.cache/cosim-gpu/disk-locks``);
- render each process's executable, arguments, environment, readiness probes,
  memory regions, disk targets and lock paths.

``cosim run <yaml> --dry-run`` prints this JSON plan without starting anything,
which is useful for checking arguments and paths before a run;
``cosim graph`` prints the machines and device connections as a Mermaid
diagram.

Starting the session
--------------------

.. mermaid::

   sequenceDiagram
       participant L as Launcher
       participant D as Device
       participant H as QEMU vHost
       participant P as Memory pool
       L->>P: reserve capacity
       L->>D: start and probe
       D->>D: create vfio-user socket
       D-->>L: lease
       L->>H: start after all leases
       H-->>L: QMP ready
       Note over L,H: session runs
       L->>H: stop vHost
       H-->>D: release lease
       L->>D: stop device
       L->>P: delete memory pool

The startup order is fixed:

1. Create the run directory under a temporary name, write ``session.lock``,
   ``plan.json``, ``options.json`` and ``manifest.json``, then publish it by
   rename.
2. Create the memory pool directory with an ownership marker and reserve
   capacity for every machine.
3. Prepare disks: create a qcow2 overlay per machine, or use the read-only or
   direct-write images declared by each vHost; ``create: true`` creates missing
   images with ``qemu-img``.
4. Start device processes in their own process groups via
   ``setpriv --pdeathsig KILL`` so they end with the launcher.
5. After a device passes its probes it hands out leases; the vHost starts once
   it holds the leases of every device on its machine.
6. The vHost negotiates QMP, optionally waits for a ``serial.wait_for``
   marker, and then runs.

Readiness probes and leases
---------------------------

- Probes run in order: output log marker, socket existence and QMP
  negotiation; the vHost can also wait for configured OS serial output.
- Each probe must succeed within ``--ready-timeout`` (120 seconds by
  default) after the process starts; the vHost serial marker can use
  ``serial.timeout`` for its own deadline.
- A ready device hands a lease to each dependent; it stops only after the
  last lease is released, so the vHost always stops before its devices.
- Machines do not wait for each other; a vHost exiting with status 0 ends only
  its own machine.

Shutdown and session end
------------------------

- The first SIGINT or SIGTERM starts an ordered shutdown; later signals skip
  the remaining wait time.
- Each process group receives SIGTERM first and SIGKILL after 5 seconds.
- ``--run-for`` limits the runtime after every process is ready; the
  development container sets a standard-input lifeline, so the session ends
  when its client exits.
- The vHost exiting with status 0 ends its machine; any other exit, a failed
  probe or a failed disk preparation cancels the whole session.
- At the end sockets, overlays and the memory pool are deleted while logs and
  metadata are kept.

Artifacts and verdict
---------------------

.. list-table::
   :header-rows: 1

   * - Path
     - Content
   * - ``plan.json``, ``options.json``
     - Execution plan and run options
   * - ``manifest.json``
     - Resource inventory created by the session, used by ``clean``
   * - ``<machine>/layout.json``
     - Memory pool regions, offsets and sizes for that machine
   * - ``<machine>/vhost/output.log``, ``<machine>/<device>/output.log``
     - Command output of the vHost and device processes
   * - ``<machine>/vhost/serial.log``
     - vHost OS serial log
   * - ``verdict.json``
     - Status, processes that did not stop and cleanup errors

The launcher prints a final ``[COSIM_VERDICT]`` line that matches
``verdict.json``. After the launcher is killed or exits abnormally, run
``cosim clean <run-dir>`` to remove resources listed in the manifest; it runs
only after the launcher and all its processes have exited and released
``session.lock``.

Related pages
-------------

- :doc:`components`
- :doc:`memory_model`
- :ref:`Session lifecycle and resources <launcher-session-lifecycle>`
- :ref:`Debugging sessions <launcher-debugging-sessions>`
- :ref:`How to write a topology YAML <topo-write-topology>`

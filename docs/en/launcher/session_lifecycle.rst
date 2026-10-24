.. SPDX-License-Identifier: Apache-2.0

.. _launcher-session-lifecycle:

Session lifecycle
==================

This page follows ``cosim run`` from publishing the session directory to writing the verdict, focusing on process order, readiness probes, leases, signals, disk overlays and resource cleanup.

Startup Order
--------------

.. mermaid::

   sequenceDiagram
       participant L as Launcher
       participant D as Device process
       participant H as Host QEMU
       L->>D: start
       D->>D: readiness probes
       D->>H: lease
       L->>H: start when all leases are held
       H->>H: QMP and serial probes
       Note over L,H: running
       L-->>H: cancellation, run-for deadline or host exit
       H->>H: shutdown
       H-->>D: release lease
       D->>D: shutdown after the last lease is released
       L->>L: remove overlays and pools, write verdict

Run Directory and Resource Publication
---------------------------------------

- The run directory is created under a temporary name, holds ``session.lock`` and receives complete ``manifest.json``, ``plan.json`` and ``options.json`` files.
- The directory is published with one rename before any external resource is created, so a visible session directory always has complete metadata.
- The launcher then creates the pool directory, reserves each pool capacity and prepares the disks.
- The pool directory is prepared under a temporary name with its ownership marker and renamed into place without replacing an existing directory, so it never appears without the marker.
- Pool storage is reserved before any simulator starts. Concurrent sessions share the filesystem capacity, and a failed reservation releases the resources of that session.

Process Supervision and Readiness
----------------------------------

- A process starts when every dependency is ready. Each device precedes its host, and the host depends on all devices of its machine. Machines do not wait for each other.
- Probes run in order: an output log marker, the existence of a Unix socket and QMP negotiation. The host additionally waits for the serial marker configured by ``serial.wait_for``.
- Every probe must succeed within ``--ready-timeout`` of the process start; the serial marker uses ``serial.timeout`` when it is set.
- A ready device hands a lease to each dependent and stops after the last lease is released, so hosts always stop before their devices.

Shutdown and Signals
---------------------

- A host that exits with status 0 ends its machine. Any other exit, a failed probe or a failed disk preparation cancels the session.
- Cancellation during disk preparation stops ``qemu-img`` and ends the session without recording a failure.
- The first SIGINT or SIGTERM starts graceful shutdown; later signals skip the remaining grace periods.
- ``--run-for`` bounds the run time after every process is ready. ``--stdin-lifeline`` (set by the development container) ends the session when standard input closes.
- Each process group receives SIGTERM, has five seconds to exit, then receives SIGKILL. Children start through ``setpriv --pdeathsig KILL`` and die with the launcher.
- ``cosim run`` requires Linux with glibc and ``setpriv``.

Sessions in the Development Container
--------------------------------------

The recipes that build, run topologies and check Rust code execute through ``scripts/host/dev.sh``. They run natively on Linux when the dependencies are installed. Other systems, or Linux with ``COSIM_ENV=container`` set, use a temporary development container.

- The source tree is mounted at its host path and ``COSIM_WORKSPACE`` points at the repository root, so paths in YAML, plans and logs are identical inside and outside the container.
- The container uses its own ``/dev/shm``, sized to the Docker daemon memory; pools disappear with the container. ``/dev/kvm`` is passed through when present.
- Outside ``--tty`` mode, ``dev.sh`` keeps the container standard input open while the Docker client runs and sets ``COSIM_STDIN_LIFELINE=1``, so the launcher stops when the client disappears.
- When the launcher exits for any reason, the container init process exits and the kernel stops every remaining process in the container, so no orphan children remain.
- ``just dev-shell`` opens a shell in a temporary container named ``cosim-dev-<random>`` that can be entered with ``docker exec``.

Disks, Overlays and Locks
--------------------------

- ``readonly: true`` opens the source image read-only. ``readonly: false`` requires ``shared: false`` and writes ``path`` directly.
- When a disk declares ``backing`` or the vHost sets ``snapshot: true``, the session writes a per-machine qcow2 overlay in its directory instead.
- A disk without ``readonly`` also gets a per-machine qcow2 overlay. ``shared: true`` requires ``readonly: true``.
- ``create: true`` with ``size`` creates a missing image with ``qemu-img``: the image is formatted under a temporary name and published with a link that never replaces an image created concurrently.
- The disk lock directory is selected by ``COSIM_DISK_LOCK_DIR``, default ``~/.cache/cosim-gpu/disk-locks``. Lock files outlive sessions, so the lock directory must be outside the pool directory.
- Image leases are keyed by device and inode. A lease lasts while the launcher or a host or helper that may use the image is alive.

Cleanup and Session Records
----------------------------

- After every process has stopped, sockets, overlays, pools and the pool directory are removed; logs remain.
- If termination cannot be confirmed, resources are kept and ``verdict.json`` records ``users_stopped: false``.
- After the launcher was killed or exited abnormally, ``cosim clean <run-dir>`` removes the resources listed in ``manifest.json``. It proceeds only after the launcher and all of its processes have exited and released ``session.lock``.
- ``clean`` removes pools only from a pool directory whose ownership marker names this session; a directory published by another session under the same name is left untouched.

.. list-table::
   :header-rows: 1

   * - Session file
     - Contents
   * - ``plan.json``
     - The executed plan: programs, arguments, environments, dependencies, probes and memory regions.
   * - ``options.json``
     - Run options: readiness timeout, run duration and the ``qemu-img`` tool.
   * - ``manifest.json``
     - The resources that ``clean`` may remove.
   * - ``<machine>/layout.json``
     - Name, offset and size of every memory region of one machine.
   * - ``<machine>/<node>/output.log``
     - Combined standard output and standard error of one process.
   * - ``<machine>/vhost/serial.log``
     - Serial console log of the host QEMU process.
   * - ``verdict.json``
     - The final result, also printed by the ``[COSIM_VERDICT]`` line.

Sources
--------

- Session execution and the verdict: ``crates/cosim-runtime/src/session.rs``.
- Process nodes, dependencies and probes: ``crates/cosim-runtime/src/node.rs`` and ``probe.rs``.
- Resource owners and locks: ``crates/cosim-runtime/src/resource.rs`` and ``process.rs``.
- Disk preparation and overlays: ``crates/cosim-runtime/src/disk.rs``.
- Cleanup: ``crates/cosim-runtime/src/manifest.rs``.

Related Pages
--------------

- :doc:`yaml_pipeline` for how the plan is produced.
- :doc:`debugging_sessions` for locating failures from logs and verdicts.
- :ref:`arch-execution-flow` for the system view of session execution.
- :ref:`arch-memory-model` for pools and the shared memory model.
- :ref:`gs-platform-container` for the development container environment and limits.
- :ref:`ref-files-and-artifacts` for session directories, build artifacts and lock directories.

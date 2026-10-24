.. SPDX-License-Identifier: Apache-2.0


.. _topo-machines-host-only:

host-only machine
=================

Overview
--------

``host-only`` is the legacy filename of a device-less TCG machine: one ``vhost-x86-tcg`` vHost starts paused, with no devices and no OS. It validates the session chain itself: the QEMU process, the memory pool, and QMP and serial management.

Topology
--------

.. code-block:: yaml

   # resources/machines/host-only.yaml
   version: 1
   imports: [vhosts/qemu.yaml, vhosts/vhost-x86-tcg.yaml]
   templates:
     vhost-x86-node:
       vhost: {use: vhost-x86-tcg}
   machines:
     - {id: m0, use: vhost-x86-node}

- Machine count: one (``m0``); there is a host only and no ``devices`` list.
- ``vhost-x86-tcg`` inherits the Q35 machine and memory map from ``vhost-x86`` and overrides only memory, CPU, accelerator and the executable.
- The vHost starts paused with ``-S -nodefaults`` and has no image or kernel, so no guest OS runs.

Hardware resources
------------------

.. list-table::
   :header-rows: 1

   * - Resource
     - Value
     - Source
   * - Machine
     - 1 (``m0``)
     - ``resources/machines/host-only.yaml``
   * - vHost profile
     - ``vhost-x86-tcg``: ``q35``, ``tcg``, ``qemu64`` CPU
     - ``resources/vhosts/vhost-x86-tcg.yaml``
   * - Guest RAM
     - 64 MiB
     - ``resources/vhosts/vhost-x86-tcg.yaml``
   * - vCPUs
     - 1
     - Same file
   * - Devices
     - None
     - —
   * - Memory pool
     - 64 MiB
     - Host RAM
   * - Executable
     - ``qemu-system-x86_64`` (looked up in ``PATH``)
     - ``resources/vhosts/vhost-x86-tcg.yaml``
   * - vHost
     - None
     - —

Software stack
--------------

- There is no guest OS: the host stays paused at QEMU startup and never runs a kernel.
- Readiness probes cover the QEMU side only: the serial socket exists and QMP negotiation succeeds; there is no ``serial.wait_for`` marker.
- The board exercises session supervision: run directory and pool creation, QMP management, process-group shutdown and resource cleanup.

Running this machine
--------------------

.. code-block:: bash

   # Validate and preview only
   just run-cli validate resources/machines/host-only.yaml
   just run-topology resources/machines/host-only.yaml --dry-run
   # Run for one second and end the session (the host is paused)
   just run-topology-dev resources/machines/host-only.yaml --run-for 1

- ``--run-for`` starts counting after every process is ready, which suits this guest-less smoke run.
- After the session, ``plan.json``, ``layout.json``, ``output.log`` and ``verdict.json`` remain, while the pool and sockets are removed.
- The lifecycle is described in :ref:`launcher-session-lifecycle`.

Verification
------------

- The plan output is one host process and zero device processes with a 64 MiB pool.
- The session test suite runs this path with TCG hosts, and there is a two-machine variant in ``tcg-pair.yaml``, see :doc:`../multi_machine`.
- The final verdict records process stop state; when termination cannot be confirmed, resources are kept and ``users_stopped: false`` is recorded.

Limitations
-----------

- The host is paused and runs no guest; use boards such as ``single-gpu`` when guest behavior is needed.
- Only TCG acceleration is exercised; the KVM guest path is not covered.
- There are no devices, so the vfio-user device path is not covered; see :doc:`qemu_device` for that sample.
- Running a session needs Linux glibc and ``setpriv``.

Related pages
-------------

- vHost profiles: :doc:`../hosts/index`
- Machine catalog: :doc:`index`
- qemu-device board: :doc:`qemu_device`
- Multi-machine variant: :doc:`../multi_machine`
- Session lifecycle: :ref:`launcher-session-lifecycle`
- Sources: ``resources/machines/host-only.yaml``, ``resources/vhosts/vhost-x86-tcg.yaml``

.. SPDX-License-Identifier: Apache-2.0

.. _sim-qemu-device-models:

QEMU device models
===================

This page describes how QEMU exports a functional device model: the ``qemu-device`` adapter starts a ``-machine x-remote`` process and exposes one PCI device to the host QEMU through ``x-vfio-user-server``. This mode guarantees functional correctness without a timing model.

Launch Form
------------

The ``qemu-device`` adapter renders ``args.device`` into QEMU device properties and starts a command of the following shape:

.. code-block:: text

   -machine x-remote,vfio-user=on,auto-shutdown=off
   -nodefaults -display none
   -qmp unix:<run-dir>/m0/<device>.qmp.sock,server=on,wait=off
   -device {"driver":"edu","id":"device0"}
   -object {"qom-type":"x-vfio-user-server","id":"vfio0",
            "socket":{"type":"unix","path":"<run-dir>/m0/<device>.sock"},
            "device":"device0"}

- ``args.device.driver`` is required; ``id`` defaults to ``device0`` when omitted.
- ``args.extra`` appends additional QEMU arguments, and ``runtime.binary`` must be a QEMU built with the vfio-user server.
- The adapter accepts no ``config`` and no private memory regions. A ``role: device`` command template kind is the way to supply private memory.
- ``auto-shutdown=off`` keeps the server running after the last client disconnects, so the launcher stops it through process-group ownership.

Example: the edu Device
------------------------

``resources/devices/pci/qemu-edu.yaml`` uses the ``edu`` educational PCI device shipped with QEMU. It provides configuration space, BARs, DMA and interrupts, enough to exercise the vfio-user configuration, MMIO and interrupt paths. The matching machine sample is ``resources/machines/qemu-device.yaml``: a paused x86_64 TCG host connected to one ``edu`` device.

Readiness and Lifetime
-----------------------

- Readiness probes are: an optional ``ready_log`` marker, the existence of the Unix socket, and QMP capability negotiation.
- Devices start before the vHost, and the vHost starts once every device is ready.
- The host stops first; the launcher then stops the device processes. Each side has its own QMP socket and logs.
- The device process has no guest memory view; DMA and configuration accesses are exchanged with the host over vfio-user.

Scope
------

- Functional simulation: device registers, BARs and interrupts behave correctly, with no timing or performance model.
- Suitable for protocol validation, driver-path validation and inexpensive integration tests.
- For MI300X command processing, cache or memory hierarchy behavior, use the performance model adapter described in :doc:`../gem5/index`.

Sources
--------

- Adapter implementation: ``crates/cosim-topology/src/adapter/qemu_device.rs``.
- Example device template: ``resources/devices/pci/qemu-edu.yaml``.
- QEMU vfio-user server: ``third_party/qemu/hw/remote/vfio-user-obj.c``.
- edu device: ``third_party/qemu/hw/misc/edu.c``.

Related Pages
--------------

- :doc:`vhost` for the host QEMU runtime.
- :doc:`index` for the two QEMU roles.
- :doc:`../gem5/index` for gem5 performance simulation.
- :ref:`topo-machines-qemu-device` for the qemu-device machine sample.
- :ref:`ref-device-adapters` for the device adapter contract.

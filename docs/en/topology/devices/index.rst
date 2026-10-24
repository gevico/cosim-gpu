.. SPDX-License-Identifier: Apache-2.0


.. _topo-devices:

Device catalog
==============

A device is a PCI model exported to a QEMU host over vfio-user. This page lists device kinds and configuration facts; the PCI/BAR interface, model coverage and guest driver requirements are described in chapter 4, and the device adapter contract is in :ref:`ref-device-adapters`.

Device kinds
------------

.. list-table::
   :header-rows: 1

   * - Device
     - kind
     - Description
     - Model details
   * - ``mi300x``
     - ``gem5-mi300x``
     - gem5 MI300X performance model; one GPU per process
     - :ref:`sim-gem5-pci`, :ref:`sim-gem5-model`
   * - ``qemu-edu``
     - ``qemu-device``
     - QEMU ``edu`` functional device; validates the vfio-user path and option ROM
     - :ref:`sim-qemu-device-models`
   * - Declared device kind
     - ``role: device`` under ``kinds``
     - Extension point with a custom ``argv`` or ``command``; no repository sample uses it yet
     - :ref:`ref-device-adapters`

- ``resources/devices/gpu/mi300x.yaml`` provides the ``mi300x`` and ``mi300x-aarch64`` templates; the latter overrides only the gem5 binary.
- ``resources/devices/pci/qemu-edu.yaml`` provides the ``qemu-edu`` and ``qemu-edu-aarch64`` templates; the former needs a QEMU built with vfio-user support.

Device fields
-------------

.. list-table::
   :header-rows: 1

   * - Field
     - Required
     - Description
   * - ``kind``
     - yes
     - Built-in ``gem5-mi300x`` or ``qemu-device``, or a device kind declared under ``kinds``
   * - ``id``
     - no
     - Defaults to the ``use`` name or kind plus an ordinal; an explicit id is kept when count is one
   * - ``use``, ``count``
     - no
     - Selects a template; count expands one entry into several device processes
   * - ``config``
     - for gem5-mi300x
     - gem5 configuration file; ``qemu-device`` rejects the field
   * - ``runtime.binary``
     - except gem5-mi300x
     - gem5-mi300x defaults to ``gem5.opt``; a bare name is looked up in ``PATH``
   * - ``runtime.argv``, ``runtime.command``
     - no
     - Overrides the adapter command; such commands need ``ready_log``
   * - ``memory_regions``
     - for gem5-mi300x
     - Exactly one region named ``vram`` with a power-of-two size; ``qemu-device`` rejects private regions
   * - ``pci``
     - no
     - vendor_id, device_id, msix_vectors and rom; MI300X values must match the hardware when set
   * - ``args``
     - no
     - Adapter-specific arguments, see :ref:`ref-device-adapters`
   * - ``guest_hints``
     - no
     - modprobe parameters and cmdline hints; cmdline requires a vHost image or kernel
   * - ``pci.rom``
     - no
     - Host-side option ROM, exposed as the vfio-user client romfile

Launch and readiness contract
-----------------------------

- The built-in ``gem5-mi300x`` and ``qemu-device`` adapters generate the launch command; a declared device kind provides ``argv`` or ``command``.
- Every device process starts before its host. Readiness probes run in order: the output log marker (``ready_log``, by default the MI300X listener line for gem5), socket existence, and QMP negotiation for ``qemu-device``.
- A ready device hands a lease to each host that depends on it; the device exits when its last lease is released after the host stops.
- Every device program must stay in the foreground, keep its resource users in its process group and keep inherited file descriptors open.
- The host template passes ``pci.rom`` as the vfio-user client ``romfile``, which the guest can read through the device ROM BAR; the launcher checks that the file exists before allocating session resources.

Devices and the memory pool
---------------------------

- Device regions follow guest RAM in declaration order. A region's full name combines the device id and the region name, for example ``mi300x-0.vram``.
- MI300X defaults to 16 GiB VRAM and ``gpu-8`` overrides each device to 8 GiB; ``qemu-edu`` has no private region.
- Region sizes, offsets and alignment are written to ``layout.json`` in the session directory; the arithmetic is in :doc:`../single_machine`.

Choosing a device
-----------------

- For the GPU performance model and the ``amdgpu`` driver path, use ``gem5-mi300x``; samples are :doc:`../machines/single_gpu` and :doc:`../machines/gpu_8`.
- To validate the vfio-user device path or option ROM, use the ``qemu-device`` ``edu`` sample in :doc:`../machines/qemu_device`.
- For a custom launch command, declare a device kind and provide ``ready_log``; no repository sample uses this path yet, and the contract is in :ref:`ref-device-adapters`.
- Model details are in chapter 4: PCI/BAR in :ref:`sim-gem5-pci`, the performance model in :ref:`sim-gem5-model`, QEMU functional devices in :ref:`sim-qemu-device-models`, and driver requirements in :ref:`sim-guest-driver`.

Related pages
-------------

- Machine catalog: :doc:`../machines/index`
- vHost profiles: :doc:`../hosts/index`
- Writing topologies: :doc:`../write_topology`
- Adapter contract: :ref:`ref-device-adapters`
- Sources: ``resources/devices/gpu/mi300x.yaml``, ``resources/devices/pci/qemu-edu.yaml``, ``crates/cosim-topology/src/adapter/``

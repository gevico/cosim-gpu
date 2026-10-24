.. SPDX-License-Identifier: Apache-2.0

.. _arch-vfio-user:

vfio-user interface
===================

vfio-user is the bridge between host QEMU and the device models. QEMU uses
the built-in client and the device side serves the protocol; it runs over a
Unix socket, while the data plane uses file descriptors and shared mappings.

Roles
-----

.. list-table::
   :header-rows: 1

   * - Role
     - Implementation
     - Detail
   * - Host client
     - QEMU ``vfio-user-pci``
     - One client per device on the host machine, connected to the device socket
   * - gem5 server
     - ``MI300XVfioUser``
     - libvfio-user based; exposes MI300X configuration space, BARs, DMA and interrupts
   * - QEMU server
     - ``x-vfio-user-server``
     - A device QEMU process exports a functional PCI model such as ``edu``
   * - Runtime
     - ``cosim-runtime``
     - Generates socket paths, controls startup order, probes readiness and deletes sockets

Connection and lifecycle
------------------------

- Each device has its own Unix socket in the machine subdirectory of the
  session directory, for example ``<run-dir>/<machine>/<device>.sock``;
- Unix sockets and shared file mappings require host and device processes on
  the same system; there is no network transport;
- the QEMU vHost command is rendered by the vHost template: one PCIe root port
  and one ``vfio-user-pci`` client per device, with the socket path and an
  optional ``romfile``;
- devices start first and the vHost starts only after the listening log and
  socket existence probes pass; shutdown stops the host, then the devices,
  and finally deletes the sockets;
- device capabilities must be registered before the vfio-user context is
  realized; PCIe root ports reserve slots ``0x10`` through ``0x17`` for
  devices.

Protocol operations
-------------------

.. list-table::
   :header-rows: 1

   * - Operation
     - Interface
     - Use
   * - PCI configuration and MMIO
     - vfio-user messages
     - Enumerate the device and access registers
   * - Doorbell access
     - Device BAR callbacks
     - A guest doorbell write triggers device work
   * - Guest RAM sharing
     - ``DMA_MAP`` with fd and offset
     - Device models access guest memory
   * - Mappable BAR regions
     - Region fd and mmap offset
     - QEMU maps large regions such as VRAM
   * - MSI-X interrupts
     - IRQ eventfd registration and notification
     - The device injects interrupts into the guest

The MI300X BAR layout (VRAM, doorbells, MSI-X and MMIO) is documented in
:ref:`MI300X PCI interface <sim-gem5-pci>`.

From doorbell to interrupt
--------------------------

.. mermaid::

   sequenceDiagram
       participant G as Guest driver
       participant H as Host QEMU
       participant D as Device model
       participant M as Shared pool
       G->>M: write command ring and descriptors
       G->>H: write doorbell BAR
       H->>D: vfio-user message
       D->>M: read commands and run DMA
       D->>H: notify IRQ eventfd
       H->>G: inject MSI-X interrupt
       G->>M: read completion and IH records

The interrupt handler writes an IH record into shared guest memory, updates
the write pointer and triggers the registered eventfd through the device
model; with KVM, QEMU turns that notification into an interrupt injection.

DMA mapping
-----------

``DMA_MAP`` carries the guest memory file descriptor and file offset, so a
device model can translate guest physical addresses into its own access to
the shared file. Devices do not copy guest memory and QEMU does not forward
every DMA. Pool layout and offsets are described in
:doc:`memory_model`.

Why vfio-user
-------------

Using the upstream protocol keeps QEMU's ``vfio-user-pci`` unchanged and
requires device implementations only to implement the protocol; shared
memory, DMA and interrupts are all expressed by standard operations. The
trade-offs are analyzed in :doc:`design_decisions`.

Related pages
-------------

- :doc:`design_decisions`
- :doc:`memory_model`
- :ref:`QEMU as device model <sim-qemu-device-models>`
- :ref:`MI300X PCI interface <sim-gem5-pci>`
- :ref:`Legacy shell launcher <launcher-legacy>`

.. SPDX-License-Identifier: Apache-2.0

.. _arch-design-decisions:

Design decisions
================

This page explains why the system splits work between QEMU and gem5, why it
connects them with vfio-user, why it uses shared memory pools and a Rust
launcher, and what limits those choices impose.

Functional and performance simulation
-------------------------------------

**QEMU handles functional simulation.** Host QEMU runs real Linux on KVM (or
TCG), performs PCIe enumeration, loads the amdgpu driver and executes ROCm
programs; device QEMU processes provide correct PCI registers and interrupt
behavior. Functional simulation answers whether a program is correct, not
how fast it is.

**gem5 handles performance simulation.** The MI300X command processors,
Shader/CU, caches and memory hierarchy, SDMA and interrupt paths are modeled
with timing in gem5. Performance simulation answers where time goes without
reimplementing a full bootable server.

**vfio-user is the bridge.** It turns PCI configuration space, BARs, DMA and
interrupts into a standard protocol, so QEMU's functional side and gem5's
performance side can be combined, and QEMU does not need to know whether the
peer is gem5 or another QEMU process.

Why connect with vfio-user
--------------------------

- QEMU ships both the ``vfio-user-pci`` client and the
  ``x-vfio-user-server``; the standard protocol means no maintained QEMU
  patches, and the ``qemu`` submodule tracks a clean release branch.
- Device models are replaceable: MI300X uses gem5 and ``edu`` uses QEMU, yet
  both are vfio-user devices to the host.
- The control plane runs over a Unix socket while the data plane uses fds and
  mmap, so large buffers are not copied between host and device processes.
- The cost is that host and device must run on the same system; the protocol
  offers no network transport.

Why a shared memory pool
------------------------

- VRAM must be mappable by QEMU through BAR0 and accessible to gem5 as device
  memory; file mappings satisfy both simply.
- One pool file per machine fixes guest memory and device region offsets in a
  single layout, avoiding overlap and runtime negotiation.
- Capacity is reserved before startup, so insufficient space fails during
  preparation instead of halfway through a run.
- The shared file only provides storage; caches and ordering are the device
  model's and guest software's responsibility, and VRAM access therefore
  bypasses vfio-user.

Why a Rust launcher
-------------------

- Topology validation is strongly typed: unknown fields, duplicate
  references and out-of-range counts fail before startup, and a JSON Schema
  can be exported.
- Plans are previewable: ``cosim run --dry-run`` prints executables, arguments,
  environment, probes, memory and disk targets for review before a run.
- Process supervision and resource ownership are explicit: process groups,
  parent-death signals, device leases, image leases, verdicts and ``clean``
  live in one runtime.
- Project crates inherit ``unsafe_code = forbid``; topology, runtime and CLI
  are three crates that can be replaced or extended.
- The legacy shell launcher is kept for legacy flows; see
  :ref:`Legacy shell launcher <launcher-legacy>`.

Why the machine owns its vHost
---------------------------------------------

The machine is the unit that runs: it combines one vHost with its connected
device models. The vHost therefore owns its image, kernel command line and
disks directly. This keeps per-machine boot choices explicit and avoids a
second document whose lifetime and scope would need separate rules.

Costs and limitations
---------------------

- Host and devices must be on the same system; device models cannot be moved
  to another machine.
- There is no network, xGMI or switch model between machines; remote
  placement is rejected by the local executor.
- QEMU device models are functional only and provide no timing; use gem5
  models when timing matters.
- The YAML path starts one GPU per gem5 process; the in-process multi-GPU mode
  is not used by that path.
- Memory pools are reserved for the complete layout, so large machines need
  corresponding shared-memory filesystem capacity.
- The shipped guest image targets x86_64 only, and there is no AArch64 guest
  image.

Related pages
-------------

- :doc:`components`
- :doc:`vfio_user`
- :doc:`memory_model`
- :ref:`Cosim Launcher <launcher-index>`
- :ref:`Legacy shell launcher <launcher-legacy>`

.. SPDX-License-Identifier: Apache-2.0

.. _ref-device-adapters:

Device adapters
===============

This page is the single source of truth for device and host adapter launch contracts: adapter kinds, ``kind`` names, parameters, rendered ``argv`` and readiness probe order are defined here. Hardware behaviour lives in chapter 4; this page covers the launch interface only.

Adapter inventory
-----------------

The repository ships two device adapters plus a template adapter for declared custom devices; the host side has a single ``qemu-vhost`` adapter.

.. list-table::
   :header-rows: 1

   * - Adapter
     - Kind
     - Model
     - Program
     - Readiness
     - Notes
   * - ``gem5-mi300x``
     - built-in
     - gem5
     - ``gem5.opt`` with ``mi300_cosim.py``
     - log marker, then the vfio-user socket
     - one GPU per process
   * - ``qemu-device``
     - built-in
     - QEMU
     - ``qemu-system-<arch>``
     - optional log marker, then socket, then QMP
     - ``x-remote`` plus ``x-vfio-user-server`` exporting one PCI device
   * - Template device
     - declared under ``kinds`` with ``role: device``
     - ``gem5`` or ``qemu``
     - ``argv`` or ``command``
     - log marker, then socket
     - ``runtime.argv`` or ``runtime.command`` can override any device command

gem5-mi300x
-----------

``gem5-mi300x`` starts one gem5 MI300X GPU per process; the YAML path hard-codes ``--num-gpus=1``, and multiple GPUs are multiple device processes.

.. list-table::
   :header-rows: 1

   * - Field
     - Required
     - Default
     - Notes
   * - ``config``
     - yes
     - —
     - points to ``third_party/gem5/configs/example/gpufs/mi300_cosim.py``
   * - ``runtime.binary``
     - no
     - ``gem5.opt``
     - relative to the workspace root, or searched in ``PATH`` when it contains no ``/``
   * - ``memory_regions``
     - yes
     - —
     - exactly one region named ``vram``, a power-of-two size with alignment of at least one page
   * - ``pci``
     - no
     - —
     - when set it must equal ``0x1002`` and ``0x74a0`` with 256 MSI-X vectors
   * - ``args.num_compute_units``
     - no
     - ``40``
     - 1 to 1024
   * - ``args.gem5_debug_flags``
     - no
     - ``[]``
     - gem5 debug flags written to ``--debug-flags``
   * - ``args.extra``
     - no
     - ``[]``
     - arguments appended to the ``mi300_cosim.py`` command line
   * - ``ready_log``
     - no
     - the default listener line
     - replaces the log marker used by the readiness probe
   * - ``guest_hints.modprobe``
     - no
     - —
     - recorded in the plan; the launcher does not execute it

Rendered command:

.. code-block:: bash

   gem5.opt --outdir=<node>/m5out [--debug-flags=<csv>] --listener-mode=off \
            <config> --socket-path=<device.sock> --shared-pool=<pool> \
            --pool-vram-offset=<offset> --dgpu-mem-size=<size>B \
            --mem-size=<ram>B --host-memory-ranges=<json> \
            --num-compute-units=<n> --num-gpus=1 [extra...]

Probes run in order: wait for the default log marker ``MI300XVfioUser: listening on <socket> (vfio-user protocol)`` (or the ``ready_log`` override), then confirm that the socket exists. A machine with a ``gem5-mi300x`` device requires a host ``memory_map``.

qemu-device
-----------

``qemu-device`` starts QEMU with ``-machine x-remote,vfio-user=on,auto-shutdown=off`` and exports one PCI device through the ``x-vfio-user-server`` object. The only shipped sample is ``edu``.

.. list-table::
   :header-rows: 1

   * - Field
     - Required
     - Default
     - Notes
   * - ``runtime.binary``
     - yes
     - —
     - must be a QEMU built with ``--enable-vfio-user-server``; ``just build-qemu`` produces ``build/qemu/qemu-system-<arch>``
   * - ``args.device``
     - yes
     - —
     - QEMU ``-device`` property map; must contain a non-empty ``driver``; ``id`` defaults to ``device0`` and must be a valid identifier
   * - ``args.extra``
     - no
     - ``[]``
     - arguments appended to the QEMU command line
   * - ``config``
     - no
     - —
     - rejected; device properties belong in ``args.device``
   * - ``memory_regions``
     - no
     - —
     - private memory regions are rejected; use a runtime command template instead
   * - ``ready_log``
     - no
     - none
     - optional log marker; when set it becomes the first probe

Rendered command:

.. code-block:: bash

   <qemu-system-<arch>> -machine x-remote,vfio-user=on,auto-shutdown=off -nodefaults \
     -display none -qmp unix:<qmp>,server=on,wait=off \
     -device '<args.device JSON>' \
     -object '{"qom-type":"x-vfio-user-server","id":"vfio0","socket":{"type":"unix","path":"<socket>"},"device":"<device.id>"}'

Probes run in order: the optional log marker, socket existence, then QMP negotiation. This device needs a QEMU build with ``--enable-vfio-user-server``.

Template devices and custom commands
------------------------------------

Declare a kind under ``kinds`` with ``role: device`` and provide ``argv`` or ``command`` to attach a custom model; the two are mutually exclusive and the device must declare ``ready_log``. ``runtime.argv`` or ``runtime.command`` overrides any device command and also requires ``ready_log``.

Template device context variables:

.. list-table::
   :header-rows: 1

   * - Variable
     - Meaning
   * - ``id``
     - device identifier
   * - ``machine``
     - owning machine identifier
   * - ``socket``
     - vfio-user socket path served to the host
   * - ``pool``
     - memory pool file path of the machine
   * - ``ram``
     - guest RAM region (``offset``, ``size``, ``align``)
   * - ``regions``
     - private regions of this device, indexed by name
   * - ``guest_ranges``
     - guest physical ranges used for ``--host-memory-ranges``
   * - ``args``
     - device ``args`` map
   * - ``config``
     - device ``config`` path
   * - ``model``
     - device model, ``gem5`` or ``qemu``
   * - ``run_dir``
     - session run directory
   * - ``node_dir``
     - working directory of the device node

The rendered result must be a non-empty argument vector; undefined variables are errors. Probes are the log marker followed by the socket.

vHost adapter contract
----------------------

A vHost kind must declare ``role: vhost`` and ``model: qemu`` and provide ``argv`` or ``command``; ``max_devices`` applies to vHost kinds only (64 for ``qemu-vhost``). The ``qemu-vhost`` command template allocates a PCIe root port per device first, attaches disks next, and appends ``vhost.args`` last.

vHost template context variables:

.. list-table::
   :header-rows: 1

   * - Variable
     - Meaning
   * - ``vhost``
     - validated vHost object with ``machine``, ``accel``, ``cpus``, ``args`` and related fields
   * - ``machine``
     - machine identifier
   * - ``pool``
     - memory pool file path
   * - ``ram``
     - guest RAM region
   * - ``guest_ranges``
     - guest physical ranges
   * - ``boot``
     - direct-boot configuration from the vHost, possibly empty
   * - ``disks``
     - rendered disk list with ``path``, ``format``, ``readonly``, ``bus`` and ``boot``
   * - ``devices``
     - device endpoint list with ``id``, ``socket``, ``model`` and ``pci``
   * - ``qmp`` / ``serial`` / ``serial_log``
     - QMP socket, serial socket and serial log paths
   * - ``cmdline``
     - The vHost's ``cmdline`` joined with every device ``guest_hints.cmdline``
   * - ``run_dir`` / ``node_dir``
     - session run directory and the working directory of this vHost node

A vHost program must stay in the foreground, keep resource users in its process group and keep inherited descriptors open; QEMU ``-daemonize`` is rejected.

Readiness probes and timeouts
-----------------------------

After a process starts, probes run in order and the process is ready when all pass; every probe must succeed within ``--ready-timeout`` (120 seconds by default). ``serial.timeout`` gives the serial marker its own 1 to 86400 second deadline. Devices become ready before the vHost, and the vHost stops before devices.

.. list-table::
   :header-rows: 1

   * - Probe
     - Passing condition
     - Used by
   * - ``Log``
     - the process output log contains the given marker
     - custom device commands; the optional host ``serial.wait_for``
   * - ``Socket``
     - the Unix socket path exists
     - gem5 devices, template devices, the host serial socket
   * - ``Qmp``
     - the QMP server completes capabilities negotiation
     - ``qemu-device`` devices and the host

Sources and maintenance
-----------------------

Contract definitions and adapter implementations:

- ``crates/cosim-topology/src/adapter/mod.rs``: ``Adapter``, ``Launch``, ``Probe`` and template contexts.

- ``crates/cosim-topology/src/adapter/gem5.rs``: ``gem5-mi300x`` parameters and argv.

- ``crates/cosim-topology/src/adapter/qemu_device.rs``: ``qemu-device`` parameters and argv.

- ``crates/cosim-topology/src/adapter/template.rs``: template devices and command rendering.

- ``resources/devices/``: device template samples; ``resources/vhosts/qemu.yaml``: host command template.

After a change, run:

.. code-block:: bash

   just run-topology resources/machines/qemu-device.yaml --dry-run
   just run-cli validate resources/machines/single-gpu.yaml  --assets
   just check-cosim

Related pages
-------------

- Device fields and vHost: :doc:`topology_schema`

- Guest driver parameters: :doc:`guest_parameters`

- Device catalog: :ref:`topo-devices`

- QEMU device models and the gem5 MI300X model: :ref:`sim-qemu-device-models`, :ref:`sim-gem5-model`

- MI300X PCI/BAR interface: :ref:`sim-gem5-pci`

- Rust workspace and extension points: :ref:`launcher-rust-workspace`

.. SPDX-License-Identifier: Apache-2.0

.. _ref-topology-schema:

Topology YAML schema
====================

This page is the human-readable reference for topology fields. ``cosim
schema`` prints the machine-readable JSON Schema. Unknown fields are errors.

Core structure
--------------

A topology contains reusable ``kinds`` and ``templates`` and one or more
``machines``. A machine has exactly two structural parts:

.. code-block:: yaml

   machines:
     - id: m0
       vhost: {use: vhost-x86-rocm}
       devices: [{use: mi300x}]

``vhost`` describes the QEMU virtual host, including how its operating system
starts. ``devices`` describes the separately executed device models. There is
no additional machine-content layer.

Document fields
---------------

.. list-table::
   :header-rows: 1

   * - Field
     - Meaning
   * - ``version``
     - Required integer; currently ``1``.
   * - ``imports``
     - YAML files resolved relative to the importing file and then ``--resources``.
   * - ``templates``
     - Reusable machine, vHost or device mappings. Mappings merge recursively; sequences replace.
   * - ``kinds``
     - Adapter kinds. ``role`` is ``vhost`` or ``device``; each kind provides ``argv`` or ``command``.
   * - ``machines``
     - One or more machine declarations; ``count`` expands a declaration.

Machine fields
--------------

``id`` is required and unique ignoring ASCII case. ``use`` selects a template,
``count`` defaults to one, ``vhost`` is required, ``devices`` defaults to an
empty list, and ``placement.agent`` is reserved for distributed execution.

vHost fields
------------

The base execution fields are ``kind``, ``runtime``, ``memory``,
``memory_align``, ``memory_map``, ``cpus``, ``accel``, ``machine``, ``cpu``,
``display``, ``monitor``, ``no_reboot``, ``serial`` and ``args``. The shipped
vHost kind uses QEMU.

The same ``vhost`` mapping owns its operating-system inputs:

.. list-table::
   :header-rows: 1

   * - Field
     - Type/default
     - Meaning
   * - ``image``
     - optional recipe identifier
     - Five-component path relative to ``resources/images/recipes``.
   * - ``kernel``
     - optional path
     - Kernel for direct boot when no image recipe is selected.
   * - ``initrd``
     - optional path
     - Initial RAM disk; requires ``kernel``.
   * - ``cmdline``
     - optional string
     - Kernel command line; requires ``image`` or ``kernel``.
   * - ``root_bus``
     - disk bus, default ``virtio``
     - Bus used for the root disk produced by ``image``.
   * - ``disks``
     - list, default ``[]``
     - Additional disks attached to this vHost.
   * - ``snapshot``
     - bool, default ``false``
     - Open writable declared disks through per-session overlays; explicitly
       read-only disks remain read-only.

``image`` cannot be combined with ``kernel`` or ``initrd``. At runtime its
verified disk is added as disk ``root`` and its exported kernel is used for
direct boot. Therefore an explicitly declared disk may not also use id
``root`` or set ``boot: true`` when ``image`` is selected.

Disk fields
-----------

Each disk requires a unique ``id`` and exactly one of ``path`` or ``backing``.
``format`` is ``raw`` or ``qcow2`` and defaults to ``qcow2``. ``bus`` is
``virtio``, ``nvme``, ``ide`` or ``scsi`` and defaults to ``virtio``.
``boot`` marks at most one boot disk. ``create`` requires ``path`` and
``size``. ``shared: true`` requires ``readonly: true``; direct writes require
both values to be false.

Device fields
-------------

A device may use ``id``, ``use``, ``kind``, ``count``, ``config``,
``ready_log``, ``runtime``, ``memory_regions``, ``pci``, ``args`` and
``guest_hints``. Adapter-specific requirements are documented in
:doc:`device_adapters`. A ``guest_hints.cmdline`` value requires the owning
vHost to select ``image`` or ``kernel``.

Paths and limits
----------------

Resource paths resolve against the workspace root. Relative paths may not
contain ``..``. Identifiers contain 1 to 48 ASCII letters, digits, underscores
or hyphens. The topology is limited to 4096 machines and 256 devices per
machine; a vHost kind may set a smaller ``max_devices`` limit.

Validate changes with:

.. code-block:: bash

   just run-cli schema
   just run-cli validate resources/machines/single-gpu.yaml --assets
   just check-cosim

See :ref:`ref-vhost-image-recipe` for image recipe fields.

.. SPDX-License-Identifier: Apache-2.0

.. _ref-simulator-device-recipes:

Simulator and device recipes
============================

Simulator recipes own tool builds and a generic execution entry. Device recipes
own model selection, parameters and launch contracts. Machines own device instances
and connections. vHost images remain under :ref:`ref-vhost-image-recipe`.

Directories and ownership
-------------------------

.. code-block:: text

   resources/
     images/recipes/ubuntu/24.04/x86_64/rocm/7.0/
     vhosts/qemu.yaml
     device_simulators/
       builder.py
       recipe.py
       cli.py
       gem5/
         recipe.toml
         run.py
     devices/gpu/mi300x/
       device.toml
       gem5.yaml
       gem5.py
     machines/single-gpu.yaml

``vhosts/qemu.yaml`` owns the QEMU vHost launch contract. ``gem5.yaml`` owns
MI300X's gem5 launch contract. QEMU device models keep their device parameters
in their own device configuration; they do not belong in the vHost configuration.
Simulator identifiers name a tool (``gem5``); device recipe identifiers name
``category/model/backend`` (``gpu/mi300x/gem5``).

Simulator recipes
-----------------

``device_simulators/gem5/recipe.toml`` uses ``schema = 1`` and these required fields:

.. list-table::
   :header-rows: 1

   * - Field
     - Meaning
   * - ``source.path``
     - Workspace source path: ``third_party/gem5``. The gitlink pins its revision.
   * - ``build.config``
     - gem5 capability build configuration: ``VEGA_X86``.
   * - ``build.binary``
     - Output filename: ``gem5.opt``.
   * - ``runtime.entry``
     - Entry filename in the simulator directory: ``run.py``.

The build output is ``build/gem5/<host-architecture>/VEGA_X86/``.
``GEM5_BUILD_DIR`` may select another directory under the workspace's ``build/``.
``VEGA_X86`` is a gem5 build configuration, separate from the QEMU guest ISA and
from the host architecture used to compile the executable.

``run.py --model-config <device-yaml>`` loads the selected recipe and its Python
model. The model exports ``add_arguments(parser, recipe)`` and ``build(args)``;
the latter returns a gem5 ``Root``. The generic entry owns ``m5.instantiate`` and
the simulation event loop. The MI300X model constructs the GPU, Ruby/TLB and bridge
objects plus the minimal gem5 System scaffolding; QEMU runs the guest CPU and OS.

Device recipes
--------------

``device.toml`` uses ``schema = 1``; its ``pci`` table owns shared PCI identity
and the ROM path. ``gem5.yaml`` uses topology document ``version: 1`` and contains
both a ``recipe`` mapping and the existing ``templates`` aliases:

.. list-table::
   :header-rows: 1

   * - Recipe field
     - Meaning
   * - ``simulator``
     - Tool recipe reference: ``gem5``.
   * - ``kind``
     - Device launch contract: ``gem5-mi300x``.
   * - ``model``
     - Python assembly module in the device directory: ``gem5.py``.
   * - ``ready_log``
     - Readiness log marker template.
   * - ``runtime.command``
     - MiniJinja template producing a JSON argument array; see :ref:`ref-device-adapters`.
   * - ``defaults``
     - Device defaults: VRAM, MSI-X vectors and guest driver hints.
   * - ``parameters``
     - Exposed defaults and constraints. ``integer`` has ``default``, ``min`` and
       ``max``; ``string-list`` has a string-array ``default``. Unknown names fail.
   * - ``requirements``
     - ``memory_map`` requires a vHost map. ``regions`` names the required memory
       regions and their ``power_of_two`` constraints.

Composition applies identity, backend defaults, then machine instance overrides.
Final values must satisfy the recipe constraints. PCI identity, entry and selected
model configuration cannot be replaced by an instance. Recipe paths reject parent
traversal and symlinks escaping the selected library or model directory.
The rendered command receives the simulator ``entry`` and the device YAML as
``config``. Exposed CU and VRAM defaults also feed the model's direct CLI defaults.

Selection and builds
--------------------

.. code-block:: yaml

   devices:
     - id: gpu0
       recipe: gpu/mi300x/gem5
       host_arch: x86_64
       memory_regions: [{name: vram, size: 8G}]
       args: {num_compute_units: 4}

``host_arch`` selects a native executable build for ``x86_64`` or ``aarch64`` and
defaults to the launcher's host architecture. ``runtime.binary`` permits an
explicit executable override. ``use: mi300x`` and ``use: mi300x-aarch64`` remain
aliases in ``gem5.yaml``. Current machine recipes start one process per GPU.
The MI300X assembly can construct multiple GPUs within one process using its
direct CLI; shared-pool mode currently requires one GPU. Cross-simulator device
interconnects and new process grouping are outside this split.

.. code-block:: bash

   just run-simulator-recipe
   just dev-image
   just build-gem5
   just test-simulator-recipes
   just check-cosim

``builder.py`` runs SCons through ``just build-gem5``. ``COSIM_ENV`` selects
native or shared development-container execution. The legacy launcher runs the
mounted binary, source libraries and device configuration in ``cosim-dev``;
there is no separate gem5 runtime image. The Rust launcher also runs natively or
as a whole inside that development container. Changing model configuration does
not require rebuilding gem5. CI transfers one development image with its exact
identity, the binary and checksums; its build key excludes runtime model files.

Related pages
-------------

- vHost images: :doc:`vhost_image_recipe`
- Launch contracts: :doc:`device_adapters`
- Topology fields: :doc:`topology_schema`
- Device catalog: :ref:`topo-devices`

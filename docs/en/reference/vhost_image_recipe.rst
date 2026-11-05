.. SPDX-License-Identifier: Apache-2.0

.. _ref-vhost-image-recipe:

vHost image recipes
===================

An image recipe builds an operating-system disk image with software installed,
ready for a vHost to boot. This page covers ``recipe.toml`` fields,
``provision.yml`` structure and the variables passed between them.

The builder starts the base image in QEMU, connects to this temporary VM over
SSH and runs Ansible to install software. After installation and shutdown,
the VM disk becomes the image result. Declared companion files, such as a
kernel or package inventory, are copied out and saved beside it.

CPU, memory and accelerator settings in ``provision`` apply to this temporary
build VM. The topology's ``vhost`` selects CPU, memory, boot arguments and
disk buses for later simulation runs.

Recipe identity
---------------

The directory is the recipe identifier and the single source of truth for its
platform and software version::

   resources/images/recipes/
     <distribution>/<release>/<architecture>/<software>/<software-release>/

For example, ``ubuntu/24.04/x86_64/rocm/7.0`` means Ubuntu 24.04 for x86_64
with ROCm 7.0. Do not repeat those five values in ``recipe.toml``.
The parser accepts architecture names ``x86_64``, ``aarch64`` and ``riscv64``.
An actual build also needs a matching base image, QEMU and installation steps.

Files in a recipe
-----------------

``recipe.toml``
   Declares the base image, build entry point, build-time variables and the
   files exported by a successful build.

``provision.yml``
   The Ansible installation file; a playbook is Ansible's name for a set of
   installation and configuration steps. ``provision.playbook`` selects its
   path.

``files/``
   Scripts, services and configuration copied into the image by the playbook.

Installation and boot initialization happen at different times.
``provision.yml`` installs software while building the image. It can also
copy an ``initialize`` script and enable a systemd service so future vHosts
run initialization automatically. The current GPU initialization sequence is
documented in :ref:`ref-guest-parameters`.

.. _ref-vhost-recipe-toml:

recipe.toml fields
------------------

The three sections in ``recipe.toml`` are ``base`` for the base image,
``provision`` for preparing the build VM and running installation, and
``result`` for declaring exported files.

The required top-level integer ``schema`` identifies the recipe file format
version, currently ``2``. Its main purpose today is to explicitly reject old
formats: the parser accepts only ``2`` and does not migrate old recipes.
Adding a vHost, distribution or software version, or changing template values,
does not require changing ``schema``. Consider updating the format version and
migrating affected recipes only when recipe field structure changes incompatibly.

All three tables ``base``, ``provision`` and ``result`` must exist. Unknown
fields are errors. Required fields below have no implicit defaults.

Base image: base
~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Field
     - Type / required
     - Meaning and constraints
   * - ``url``
     - string / yes
     - HTTPS download address of the base disk image. The base system must
       accept installation over SSH; the shared build template uses cloud-init
       to configure a temporary login key.
   * - ``sha256``
     - string / yes
     - SHA-256 of the base image: 64 lowercase hexadecimal characters without
       a ``sha256:`` prefix.
   * - ``format``
     - string / yes
     - Base disk format: ``raw`` or ``qcow2``.

Build and installation: provision
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Field
     - Type / required
     - Meaning and constraints
   * - ``image_name``
     - string / yes
     - VM and disk filename used during the Packer build. The published disk
       is always named ``disk``.
   * - ``disk_size``
     - string / yes
     - Build disk capacity, interpreted by Packer, for example ``"40000M"``.
   * - ``disk_format``
     - string / yes
     - Result disk format: ``raw`` or ``qcow2``; it may differ from ``base.format``.
   * - ``cpus``
     - integer / yes
     - Number of vCPUs for the temporary build VM; at least ``1``.
   * - ``memory_mb``
     - integer / yes
     - Temporary build VM memory in MiB; at least ``512``.
   * - ``ssh_username``
     - string / yes
     - User Packer and Ansible use to connect to the temporary build VM.
   * - ``accelerator``
     - string / yes
     - QEMU accelerator: ``kvm``, ``tcg`` or ``hvf``. The build host must meet
       the requirements of the selected accelerator.
   * - ``machine_type``
     - string / yes
     - QEMU machine type for the build VM, for example ``q35``.
   * - ``cpu_model``
     - string / yes
     - QEMU CPU model for the build VM, for example ``host``. It must match
       the architecture and accelerator.
   * - ``playbook``
     - string / yes
     - Installation file path relative to the recipe directory, normally
       ``provision.yml``. The resolved file must exist inside that directory.
   * - ``variables``
     - table / yes
     - Installation variables described below. Keep an empty
       ``[provision.variables]`` table when there are none.
   * - ``files``
     - table / yes
     - Installation files read from outside the recipe directory, described
       below. Keep an empty ``[provision.files]`` table when there are none.

Installation variables and files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Keys in ``[provision.variables]`` are recipe-defined variable names; values
must be strings. Ansible reads them as ``cosim_recipe_variables.<name>``.
Use this table for installation parameters such as package and kernel
versions. Read the software version already encoded in the directory through
``cosim_recipe.software_release``.

Keys in ``[provision.files]`` are file aliases; values are file paths relative
to the repository workspace root, such as
``firmware = "third_party/example/firmware.bin"``. Paths cannot be absolute or
contain ``..``. Build inputs also cannot escape the workspace through symlinks.
The builder converts each path to an absolute path and passes it to Ansible as
``cosim_provision_files.firmware``. Declaring a file makes the builder check
and record the input; the playbook's ``copy`` step chooses its destination.

For EFI-based provisioning, the aliases ``efi_firmware_code`` and
``efi_firmware_vars`` select the firmware files used by Packer. Packer copies
the variable store for the temporary build VM. The topology separately selects
the boot method of simulation sessions.

Keep recipe-owned scripts, services and configuration in ``files/`` and refer
to them as ``{{ playbook_dir }}/files/<filename>``. The builder records recipe
sources and declared input contents; changes cause it to re-evaluate whether
an existing image can be reused.

The repository's ROCm 7.0 recipe uses ``[provision.files]`` to reference
``mi200.rom``, ``mi300.rom``, ``mi300_discovery`` and ``mi350_discovery`` under
``third_party/gem5-resources/src/x86-ubuntu-gpu-ml/files/``. The
``gem5-resources`` submodule supplies these files; the recipe declares their
inputs and installation destinations. The MI300X device template, ROM test
and regression provenance use the same ``mi300.rom`` from that submodule.
``just build-disk``, ``just build-rocm-assets`` and ``just test-cosim-vfio-user``
initialize it first. ``just build-gpu-app`` also reads GPU application sources
from it.

Exported files: result
~~~~~~~~~~~~~~~~~~~~~~

The installed disk is produced automatically and does not belong in
``result.files``. This list declares only additional files copied out of the
image. ``[result]`` may be empty; an omitted ``files`` defaults to an empty list.

.. list-table::
   :header-rows: 1

   * - Field
     - Type / required
     - Meaning and constraints
   * - ``kernel``
     - string / no
     - Name of the exported file used for direct kernel boot. It must match
       a ``result.files.name``. ELF kernels are checked with ``readelf``;
       RISC-V Linux Images are checked by their boot image header.
       Omit this field when no direct-boot kernel is exported.
   * - ``files``
     - list of objects / no
     - Add one ``[[result.files]]`` entry per exported file; defaults to ``[]``.
   * - ``files[].name``
     - string / required per entry
     - Unique output filename using only ASCII letters, digits, ``_``, ``.``
       and ``-``. Reserved names are ``disk``, ``manifest.json``, ``packer.log``
       and ``build.log``.
   * - ``files[].guest_path``
     - string / required per entry
     - Absolute source file path inside the temporary build VM, without ``..``.
       Here ``guest`` is ordinary terminology for the system running in QEMU.

After declaring an exported file in TOML, the playbook must fetch it as shown
below. The builder checks that all declared files were fetched before
verifying and publishing the result.

TOML structure example
~~~~~~~~~~~~~~~~~~~~~~

This example shows the field structure. Replace the URL, checksum and
external file path with actual inputs:

.. code-block:: toml

   schema = 2

   [base]
   url = "https://example.invalid/base.qcow2"
   sha256 = "0000000000000000000000000000000000000000000000000000000000000000"
   format = "qcow2"

   [provision]
   image_name = "example"
   disk_size = "40000M"
   disk_format = "qcow2"
   cpus = 4
   memory_mb = 8192
   ssh_username = "ubuntu"
   accelerator = "kvm"
   machine_type = "q35"
   cpu_model = "host"
   playbook = "provision.yml"

   [provision.variables]
   package_name = "bash"

   [provision.files]
   firmware = "third_party/example/firmware.bin"

   [result]

   [[result.files]]
   name = "image-os-release"
   guest_path = "/etc/os-release"

.. _ref-vhost-recipe-provision:

provision.yml structure and fields
----------------------------------

This file uses Ansible's YAML format. The example installs software and
exports the files declared in TOML. Each recipe supplies its own package,
driver and configuration steps:

.. code-block:: yaml

   - name: Install the image contents
     hosts: default
     become: true
     gather_facts: true
     tasks:
       - name: Install the selected package
         ansible.builtin.package:
           name: "{{ cosim_recipe_variables.package_name }}"
           state: present

       - name: Fetch declared result files
         ansible.builtin.fetch:
           src: "{{ item.guest_path }}"
           dest: "{{ cosim_result_directory }}/{{ item.name }}"
           flat: true
         loop: "{{ cosim_result_files }}"

Play-level fields
~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Field
     - Meaning in this project
   * - ``name``
     - Readable name for this group of operations, shown in build logs.
   * - ``hosts``
     - Execution target. The shared builder uses ``default`` for the temporary
       build VM. This is neither the physical build host nor the topology's
       ``vhost`` field.
   * - ``become``
     - ``true`` enables privilege escalation for installation, usually to root.
   * - ``gather_facts``
     - ``true`` collects system information, such as distribution and
       architecture, for installation steps to check and use.
   * - ``tasks``
     - Installation, configuration and file export steps executed in order.

These are Ansible fields. Full definitions are in
`Ansible playbook keywords <https://docs.ansible.com/projects/ansible-core/2.18/reference_appendices/playbooks_keywords.html>`_.

Common task fields
~~~~~~~~~~~~~~~~~~

Each task has a readable ``name`` and selects an Ansible module to perform
an operation. The current recipe uses ``package`` or ``apt`` to install
software, ``file`` to create directories, ``copy`` to install files,
``systemd_service`` to enable boot services, and ``fetch`` to export files.
Module arguments follow each module's definition, rather than a recipe-specific
schema.

.. list-table::
   :header-rows: 1

   * - Field or argument
     - Meaning
   * - ``package.name`` / ``package.state``
     - Package name and desired state; for example, ``state: present`` ensures
       the package is installed.
   * - ``file.path`` / ``file.state``
     - Path and desired state; for example, ``state: directory`` creates a directory.
   * - ``copy.src`` / ``copy.dest``
     - Local source file and installation path inside the VM. ``owner``,
       ``group`` and ``mode`` set destination ownership and permissions;
       write permissions as strings such as ``"0755"``.
   * - ``systemd_service.name`` / ``enabled`` / ``daemon_reload``
     - Service name, whether to enable it at boot, and whether to reload unit
       configuration. Enabling a service does not immediately start it.
   * - ``ansible.builtin.user.shell``
     - Sets a user's default login shell, such as ``/bin/bash``, when creating
       the user. It does not execute an installation script.
   * - ``ansible.builtin.command.argv``
     - Program and argument list, such as ``[dkms, autoinstall]``. Pipes and
       redirection are not interpreted.
   * - ``ansible.builtin.shell.cmd``
     - Command string executed through a shell, for steps requiring ``>``
       or pipes.
   * - ``loop`` / ``item``
     - Executes the task for each list entry; ``item`` is the current entry.
   * - ``register``
     - Stores a task result in a named variable so later tasks can read values
       such as ``stdout``.
   * - ``changed_when``
     - Controls when the task reports a change. It does not skip the command
       or replace failure checks.
   * - ``failed_when``
     - Controls task failure conditions. ``false`` can help collect diagnostics,
       but the actual failure must still be reported separately.
   * - ``block`` / ``rescue``
     - Groups tasks; a task failure enters ``rescue``, for example to print
       DKMS logs and then report failure.

Prefer ``command.argv`` for ordinary commands; use ``shell.cmd`` when shell
syntax is needed. See the
`Ansible command module <https://docs.ansible.com/projects/ansible-core/2.18/collections/ansible/builtin/command_module.html>`_
for its behavior.

Variables supplied by the project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The builder generates these variables. Recipes read them instead of maintaining
duplicate configuration.

.. list-table::
   :header-rows: 1

   * - Variable
     - Source and purpose
   * - ``cosim_recipe``
     - Directory-derived ``distribution``, ``release``, ``architecture``,
       ``software`` and ``software_release``. For example, use the software
       version when constructing a package repository URL.
   * - ``cosim_recipe_variables``
     - String mapping from ``[provision.variables]``.
   * - ``cosim_provision_files``
     - Mapping from ``[provision.files]`` aliases to absolute build-host paths,
       used as ``copy.src``.
   * - ``cosim_result_files``
     - List from ``[[result.files]]``; each entry contains ``name`` and
       ``guest_path``.
   * - ``cosim_result_directory``
     - Local staging directory for this build's exported files, used as
       ``fetch.dest``. The builder moves them to the final output after success.
   * - ``playbook_dir``
     - Ansible variable containing the installation file's directory.
       Recipes are copied into a staging directory during builds, so locate
       recipe-owned files relative to this variable.

File paths and transfer direction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Expression
     - Location
     - Purpose
   * - ``provision.files.firmware``
     - Path in ``recipe.toml``, relative to the repository root
     - Declares an external installation input.
   * - ``{{ cosim_provision_files.firmware }}``
     - Host running the builder
     - ``copy.src``: copies from the build host into the temporary VM.
   * - ``{{ playbook_dir }}/files/initialize.sh``
     - Staged recipe directory on the build host
     - ``copy.src`` for a recipe-owned file; this filename is only an example.
   * - ``copy.dest`` / ``fetch.src``
     - Inside the temporary build VM
     - Installation destination or the source from ``result.files[].guest_path``.
   * - ``{{ cosim_result_directory }}/{{ item.name }}``
     - Host running the builder
     - ``fetch.dest``: retrieves a file using the declared output filename.

The example's ``flat: true`` saves each fetched file at the specified name,
without adding the target hostname and original directory hierarchy. See the
`Ansible fetch module <https://docs.ansible.com/projects/ansible-core/2.18/collections/ansible/builtin/fetch_module.html>`_.

Using an image
--------------

A vHost selects the recipe directly:

.. code-block:: yaml

   vhost:
     use: vhost-x86
     image: ubuntu/24.04/x86_64/rocm/7.0
     cmdline: console=ttyS0 root=/dev/vda1 rw
     root_bus: virtio

At runtime the launcher resolves the verified recipe result. When
``result.kernel`` is declared, it uses that file for direct boot and attaches
the image disk as ``root``. Without an exported kernel, QEMU uses disk boot.
A vHost without a recipe may declare ``kernel``, ``initrd``, ``cmdline`` and
``disks`` directly. ``cmdline`` requires a direct-boot kernel. Full runtime
fields are in :ref:`ref-topology-schema`.

Commands
--------

.. code-block:: bash

   just ci-rocm-assets list
   just ci-rocm-assets inspect <recipe-id>
   just ci-rocm-assets validate <recipe-id>
   just ci-rocm-assets build <recipe-id>

``inspect`` reads configuration and cache status. ``validate`` checks Packer
and Ansible configuration. ``build`` builds the image or reuses an existing
image that passes input and integrity checks.
Build results live under ``build/images/<recipe-id>/``: ``disk`` is the
installed disk, companion files use their ``result.files[].name``, and
``manifest.json`` is a builder-generated record of recipe identity, input
fingerprint, output sizes and SHA-256 checksums. These files are not source.

Related pages
-------------

- Adding a recipe: :ref:`contrib-add-vhost-recipe`
- Runtime machine fields: :ref:`ref-topology-schema`
- GPU initialization after boot: :ref:`ref-guest-parameters`
- File and artifact paths: :doc:`files_and_artifacts`

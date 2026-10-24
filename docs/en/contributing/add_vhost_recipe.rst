.. SPDX-License-Identifier: Apache-2.0

.. _contrib-add-vhost-recipe:

Add a vHost image recipe
========================

Use this workflow when a new distribution, architecture or software version
needs a different image build. A runtime-only difference belongs in a vHost
template, not in a new recipe.

1. Choose the identifier
------------------------

Create exactly this five-level directory::

   resources/images/recipes/
     <distribution>/<release>/<architecture>/<software>/<software-release>/

The path is the identity. Do not add a second identifier or repeat its parts
inside ``recipe.toml``.

2. Declare the build
--------------------

Add ``recipe.toml`` following :ref:`ref-vhost-recipe-toml` to declare the base
image, installation parameters and exported files. Pin the base image's
SHA-256 and make sure the selected CPU, memory, disk capacity and accelerator
meet the requirements of this image build.

Keep recipe-owned scripts, services and configuration in ``files/`` and
reference them from ``provision.yml`` through ``{{ playbook_dir }}/files``.
Use one playbook; do not introduce a second task-entry file unless the build
has a demonstrated reusable split.

3. Install the image contents
-----------------------------

Write ``provision.yml`` following :ref:`ref-vhost-recipe-provision` to install
the operating-system packages, kernel, drivers and services needed by the
vHost. Read the variables supplied by the recipe and fetch declared exported
files in the final task.

When boot initialization is needed, install an ``initialize`` script and its
systemd service into the image, then enable the service. Software installation
happens during image construction; future vHosts run boot initialization.

Do not add full-system gem5 support or simulator-specific control utilities to
the image. The project runs the operating system in QEMU and connects device
models separately.

4. Connect a vHost sample
-------------------------

Add or update a template under ``resources/vhosts/``:

.. code-block:: yaml

   templates:
     vhost-example:
       use: vhost-x86
       image: <distribution>/<release>/<architecture>/<software>/<software-release>
       cmdline: console=ttyS0 root=/dev/vda1 rw
       root_bus: virtio

Machine samples then select that vHost under ``machine.vhost``; its image and
boot fields remain part of the same topology.

5. Validate
-----------

Start with checks that do not build the large image:

.. code-block:: bash

   just ci-rocm-assets inspect <recipe-id>
   just ci-rocm-assets validate <recipe-id> --syntax-only
   just docs-check

``--syntax-only`` checks Packer and Ansible syntax without booting the build
VM. Its first run may download required tools. Also run the Python checks in
:ref:`contrib-ci` to exercise recipe parsing and image reuse.

Run a real image build only on a Linux KVM host or in the image CI job. After
the build, inspect the manifest and boot a machine that selects the new vHost.
Record distribution-specific findings in this guide only after they are
observed during implementation.

Related pages
-------------

- Recipe fields and installation files: :ref:`ref-vhost-image-recipe`
- CI validation workflow: :doc:`ci`
- Documentation rules and local preview: :doc:`documentation`

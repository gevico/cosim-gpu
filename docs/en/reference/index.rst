.. SPDX-License-Identifier: Apache-2.0

.. _ref-index:

Reference
=========

This chapter is the single source of truth for schemas, parameters, versions,
file paths, the GART format and known issues. Other chapters explain behaviour
and link here so that no table is maintained twice.

.. toctree::
   :maxdepth: 1

   topology_schema
   device_adapters
   vhost_image_recipe
   guest_parameters
   version_matrix
   files_and_artifacts
   gart_format
   known_issues
   legacy_launcher_flags

Recommended reading paths
-------------------------

- First guest boot or a driver that does not load: read
  :doc:`guest_parameters`, then look up the symptom in :doc:`known_issues`.
- Writing or changing a topology YAML: look up fields and defaults in
  :doc:`topology_schema`, device launch contracts in
  :doc:`device_adapters`, and the end-to-end walkthrough in
  :ref:`topo-write-topology`.
- Reproducing a build or checking version drift: start from
  :doc:`version_matrix`, then locate artifacts, logs and sources with
  :doc:`files_and_artifacts`.
- Adding or reviewing a vHost image recipe: see :doc:`vhost_image_recipe` for
  fields and artifacts, then :ref:`contrib-add-vhost-recipe` for the workflow.
- Debugging GPU address translation and GART tables: :doc:`gart_format` has
  the entry and register formats; the translation flow is in
  :ref:`sim-gem5-address-translation`.
- Maintaining or comparing the legacy shell launcher:
  :doc:`legacy_launcher_flags` is the only option table for that path.

Canonical ownership
-------------------

.. list-table::
   :header-rows: 1

   * - Page
     - Owned content
     - Primary source
   * - :doc:`topology_schema`
     - Topology and vHost fields, types, defaults and limits
     - ``crates/cosim-topology/src/raw.rs``, ``resolve.rs``
   * - :doc:`device_adapters`
     - Adapter parameters, argv and readiness probes
     - ``crates/cosim-topology/src/adapter/``
   * - :doc:`vhost_image_recipe`
     - vHost image recipe directories, fields, input identity and bundle format
     - ``resources/images/recipe.py``, ``identity.py``, ``bundle.py``
   * - :doc:`guest_parameters`
     - amdgpu module parameters, ROM write, kernel cmdline, IP block mask
     - ``tests/test_modprobe_params.sh``, image recipe
   * - :doc:`version_matrix`
     - Recorded versions, image tags and provenance
     - ``third_party/qemu/VERSION``, ``recipe.toml``, ``Cargo.toml``
   * - :doc:`files_and_artifacts`
     - Source directories, build outputs, session directories, guest files and environment variables
     - Repository layout, ``crates/cosim-runtime/src/layout.rs``
   * - :doc:`gart_format`
     - GART PTEs, aperture registers and typical layout
     - ``third_party/gem5/src/dev/amdgpu/amdgpu_vm.cc``
   * - :doc:`known_issues`
     - Issue catalog organized by symptom, cause and fix
     - Historical issue records, driver and model behaviour
   * - :doc:`legacy_launcher_flags`
     - Corrected shell-launcher and gem5-config option tables
     - ``scripts/host/cosim_launch.sh``, ``mi300_cosim.py``

Related chapters
----------------

- Using topology fields: :ref:`topo-write-topology`
- vfio-user and device models: :ref:`sim-qemu-device-models`, :ref:`sim-gem5-pci`
- Guest driver requirements: :ref:`sim-guest-driver`
- Commands and session lifecycle: :ref:`launcher-cli`, :ref:`launcher-session-lifecycle`

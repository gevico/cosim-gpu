.. SPDX-License-Identifier: Apache-2.0

.. _contrib-ci:

CI
==

This page covers the repository's GitHub Actions workflows, the fast checks, the
build caches and the ROCm regression.

Workflow overview
-----------------

.. list-table::
   :header-rows: 1

   * - Workflow
     - Trigger
     - Purpose
   * - ``docs.yml``
     - Push/PR touching ``docs/**``, ``justfile`` or the READMEs
     - Build both languages, run the bilingual and site checks; deploy GitHub
       Pages from ``main``
   * - ``ci.yml``
     - Push/PR to ``main``
     - Host-side checks under five minutes that need no submodules
   * - ``build.yml``
     - Push/PR to ``main``, or manual dispatch
     - Build gem5 ``VEGA_X86`` and the ROCm guest image, then call the
       regression
   * - ``integration.yml``
     - Called by ``build.yml`` via ``workflow_call``
     - Full ROCm guest regression on a KVM runner
   * - ``assigner.yml``
     - ``pull_request_target`` and issue label events
     - Add labels, request reviews and assign an owner from ``MAINTAINERS.yml``

Fast checks
-----------

The jobs in ``ci.yml`` run on every push and pull request:

- ``Rust Topology and Runtime``: ``just check-cosim``,
  ``just test-cosim-integration`` and ``just test-cosim-memory``.
- ``ROCm regression runner tests``: ``python3 -m unittest discover
  -s scripts/ci -p 'test_*.py' -v``.
- ``Checkpatch``: ``just check-patch`` against the pull request base or the
  pre-push commit; falls back to ``HEAD^`` when no earlier commit is available.
- ``Maintainers``: installs ``scripts/ci/requirements.txt`` and runs
  ``just check-maintainers``.
- ``ShellCheck``: runs ``just check-shell``.
- ``Modprobe Params (Regression #9)``: runs ``just check-modprobe-params``.
- ``GPU Kernel Compile``: runs ``just build-gpu-tests``.

A failing ``Checkpatch`` job blocks the pull request. Fix the reported lines,
amend or rebase the commits, and force-push the branch. The docs workflow runs
``docs/scripts/build.sh``, then ``docs/scripts/check_i18n.py`` and
``docs/scripts/verify_build.py``; builds from ``main`` are published to
GitHub Pages.

Build caches and artifacts
--------------------------

``build.yml`` has two producer jobs and one regression job:

- ``Build gem5 (VEGA_X86)`` builds gem5 once. The cache key comes from
  ``just ci-gem5-key`` and covers the gem5 inputs, the related just recipes and
  configuration, the build task, helper scripts and the Dockerfile.
  Only explicitly listed gem5 and development-container just settings are used;
  vHost recipes, image output paths and other vHost configuration do not affect
  the gem5 cache key. A cache hit
  preserves the original ``build_source`` and ``build_run``; the current
  source revision and run identity are recorded separately. Changing
  ``COSIM_GEM5_CACHE_EPOCH`` rebuilds the toolchain environment. The artifact
  contains the binary, the ``libvfio-user.a`` needed by model tests, the
  development container image and a SHA-256 manifest; ``just ci-reuse-gem5``
  publishes it as this run's immutable artifact, and
  ``just test-runtime-artifact`` verifies its integrity and provenance.
- ``Build ROCm guest image`` validates the real Packer builder and provisioners,
  then looks for a verified retained image from the same source branch. The
  image key covers source revisions, recipe contents, the QEMU version, the
  image builder and the disk format; reuse
  validates the input identity and every product hash. Changing
  ``COSIM_ROCM_IMAGE_EPOCH`` from its default ``1`` resolves packages again.
  The finished image records the resolved Debian and Python package versions and
  the SHA-256 values in ``manifest.json``.
- ``ROCm regression`` calls ``integration.yml`` with the gem5 artifact ID,
  the guest artifact ID and the image input key.
- ``ROCm regression gate`` requires the gem5 build, the image build and the
  guest execution to succeed; configure it as a required check in branch
  protection.

The ``gem5-runtime-*`` and ``rocm-guest-*`` artifacts are retained for two
days; ``rocm-image-logs-*`` and the regression evidence are retained for fourteen
days. Dispatch ``build.yml`` manually to repeat the complete pipeline.

ROCm regression
---------------

``integration.yml`` consumes the immutable artifact IDs produced by
``build.yml`` instead of rebuilding:

1. Check that the runner is x86_64 with ``/dev/kvm`` available, and initialize
   the submodules.
2. Download the gem5 artifact and restore the verified gem5 and development image
   with ``just ci-restore-gem5``.
3. Run ``just test-cosim-memory`` for competing-session memory reservations,
   then ``just test-gem5-mi300x`` for the restored MI300X model.
4. Download the guest artifact and adopt the disk, kernel and package inventory
   with ``just ci-adopt-rocm-artifact``, checking the image input key.
5. Build QEMU and the Rust launcher, run ``just test-cosim-vfio-user`` to verify
   vfio-user option ROM exposure, and run ``just test-rocm-regression``.

``just test-rocm-regression <output> <assets>`` uses the Rust launcher and the
sample host/device templates and creates a private disk overlay per case. It
defaults to 4 GiB of guest RAM, 4 GiB of VRAM and two guest CPUs; the 8 GiB pool
fits the hosted runner's shared-memory capacity and leaves memory for the
simulator. ``--memory``, ``--vram`` and ``--cpus`` override these
values.

The programs are ``vector_add``, ``gemm``, ``reduction``,
``transpose``, ``prefix_scan`` and ``histogram``. Each guest checks the
setup service, amdgpu, KFD, render devices and the gfx942 agent reported by
``rocminfo``, then compiles and executes the HIP program with
``HSA_ENABLE_INTERRUPT=0``. Success requires its numerical PASS result, a zero
process exit status, and successful launcher cleanup; a timeout after printing
PASS still fails. Execution stops at the first failure and the aggregate verdict
requires every listed program to pass.

The ``rocm-regression-*`` artifact keeps the complete serial and model logs,
topology and command manifests, source revisions, binary digests, per-program
verdicts and ``matrix.tsv``.

Reproducing locally
-------------------

.. code-block:: bash

   python3 -m unittest discover -s scripts/ci -p 'test_*.py' -v  # CI helper tests
   just test-legacy-build-image    # legacy build entry against host Docker
   just test-cosim-memory          # competing session reservations and release
   just test-cosim-integration     # sessions, cancellation and log retention
   just test-runtime-artifact <source> <output>  # runtime cache integrity and provenance
   just test-rocm-artifact <key> <output>        # image selection and isolation

   # ROCm image and regression
   just build-rocm-assets
   just test-rocm-assets
   just test-rocm-regression <output> <assets>

Related pages
-------------

- :doc:`workflow`
- :doc:`patch_check`
- :ref:`gs-guest-image`
- :ref:`ref-version-matrix`

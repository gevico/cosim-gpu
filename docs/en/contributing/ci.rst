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
     - Host-side checks; session and image-tool tests build the pinned QEMU submodule
   * - ``build.yml``
     - Push/PR to ``main``, or manual dispatch
     - Select recipe checks and run gem5/full regression when required
   * - ``image.yml``
     - Called by ``build.yml`` via ``workflow_call``
     - Validate, build or reuse one recipe and publish its image; optionally run
       ROCm regression with the local image
   * - ``assigner.yml``
     - ``pull_request_target`` and issue label events
     - Add labels, request reviews and assign an owner from ``MAINTAINERS.yml``

Fast checks
-----------

The jobs in ``ci.yml`` run on every push and pull request:

Session and image-tool tests first run ``just ci-build-qemu`` to build QEMU
and its image tools under ``build/qemu/`` from the pinned submodule.

Image builders run ``just ci-prepare-image-host <recipe>`` before Packer
validation. The recipe loader selects the guest architecture and invokes
``just ci-build-qemu <architecture>`` so a RISC-V image receives
``build/qemu/qemu-system-riscv64``, with matching source-built image tools.
The architecture selector does not change the build Host architecture.

- ``Rust Topology and Runtime``: ``just check-cosim``,
  ``just test-cosim-integration`` and ``just test-cosim-memory``.
- ``CI helper tests``: ``python3 -m unittest discover
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

Selecting recipe checks
-----------------------

``build.yml`` compares the complete PR changes against the target branch, or
the revisions before and after a push:

- Changes only under ``docs/`` or to the two READMEs skip heavy checks.
- Changes only to existing recipe directories and documentation select those
  recipes. Each selected recipe prepares an image and runs the HIP regression.
- Shared files, workflows, unknown paths, and removed or moved recipes select
  all existing recipes, each once.

Recipes come from existing ``recipe.toml`` files. Every selected recipe must
also provide ``regression.toml``; a missing profile fails selection instead of
silently skipping GPU tests. An initial push without a previous revision checks
all recipes; a failed comparison fails the check. For manual dispatch, set
``recipe`` to build or reuse and test just that recipe, or leave it empty to test
all recipes. Either path prepares gem5 and requires the HIP workloads to pass.

Each recipe job validates real Packer/Ansible configuration, prepares a verified
image, and checks artifact integrity and reuse isolation before running GPU
workloads. Packer boot alone does not prove the final image works with its
simulation topology. Jobs currently use Ubuntu x86_64 runners. Recipes still
need matching QEMU, firmware and acceleration; new platforms supply their
environment setup and regression profile.

Build caches and artifacts
--------------------------

The Ubuntu test-image recipe disables periodic APT activity before installing
packages. It stops and masks update timers, masks the corresponding services,
and waits for any running update to finish without terminating package work.
The resulting image keeps automatic updates disabled; package changes are made
through a new recipe build. Final cache cleanup still fails on error.

All selected recipes use the image and GPU regression flow in ``image.yml``:

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
- ``Image preparation and GPU regression`` validates the recipe's real Packer builder and provisioners,
  then looks for a verified retained image from the same source branch. The
  image key covers relevant file hashes, recipe contents, the QEMU toolchain,
  the image builder and the disk format; reuse
  validates the input identity and every product hash. Changing
  ``COSIM_ROCM_IMAGE_EPOCH`` from its default ``1`` resolves packages again.
  The finished image records the software versions declared by its recipe and
  the SHA-256 values in ``manifest.json``.
- ``Recipe (<recipe>)`` calls ``image.yml`` once per selected recipe. Image
  preparation starts alongside gem5 and synchronizes before GPU testing.
  CI helper tests are a separate host-side check, labelled ``CI helper tests``.
- ``ROCm regression gate`` always runs and rejects failed or cancelled jobs.
  Jobs skipped by the selection conditions do not block it. Configure this gate
  as a required check in branch protection.

The ``gem5-runtime-*`` and ``rocm-guest-*`` artifacts are retained for two
days; ``rocm-image-logs-*`` and the regression evidence are retained for fourteen
days. Dispatch ``build.yml`` manually for the full pipeline, or supply
``recipe`` to check a single recipe. Image artifact names contain a digest of
the recipe identifier so one run can publish several recipes independently.

Image reuse also works across CI runs on the same source branch. The input key
does not contain the project commit or CI run ID, and CModel source is not an
image input. A CModel-only change can therefore reuse a matching image built by
an earlier run. The new runner still downloads the bundle and verifies its
identity and hashes. Missing, expired or changed inputs cause a new image build;
there is no fallback that skips HIP tests. The current two-day image retention
and source-branch isolation still apply.

ROCm regression
---------------

Each image and its regression run in one job so the verified disk and kernel
stay on the runner's local filesystem. GitHub-hosted jobs each receive a
`fresh runner instance <https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job>`_;
matching ``runs-on`` labels and ``needs`` dependencies do not colocate jobs.
A unique label can target one persistent self-hosted runner, but file retention
and cleanup would then be our responsibility.

Image preparation and the separate gem5 job run concurrently. The image job has
no gem5 ``needs`` dependency: after preparing its local image, it runs
``just ci-wait-gem5``. This queries the latest gem5 producer execution in the current run up to the
current attempt, fails if it failed or was cancelled, and waits at most two hours
for success and its matching immutable artifact. Retrying only failed jobs may
reuse the successful producer from an earlier attempt of the same run. GitHub
may copy its successful job record into the new attempt without executing it
again. Records with the same start and completion times identify that original
execution; its artifact retains the original attempt number. Only then does it
download and restore gem5. No background step is required: gem5 was already running while the
image was being prepared. The normal regression gate still requires all jobs.

This preserves parallel preparation without transferring the system disk to a
second runner. In the motivating run, gem5 runtime download took about one
minute and guest-image download about fifty minutes; these are observations,
not transfer guarantees. Images are still published for reuse by later runs,
which verify exact inputs and every product hash. Each recipe job allows five hours for image preparation and regression.

A recipe opts into full GPU regression through ``regression.toml`` beside its
``recipe.toml``. It references a machine YAML under ``resources/machines`` and a
guest preparation script in its own recipe directory. Machine/vHost templates
own boot parameters; the runner selects QEMU using the image recipe architecture
and verifies the selected bundle. It does not infer boot settings from Ubuntu
or from the build Host. Ubuntu prepares its initialization service and ROM;
openRuyi prepares its native compiler environment and loads amdgpu. Both recipes
provide root serial console access. The common ``tests/rocm_regression.sh`` is
shared through read-only 9p and owns GPU checks, compilation and execution.

The combined job performs these steps:

1. Prepare source-built QEMU and image tools; validate Packer, build or adopt a
   retained image, and check image integrity, reuse and source isolation.
2. Publish the image for later runs while retaining its local disk and kernel.
3. Synchronize with this run's successful gem5 producer, download its immutable
   runtime artifact and restore the verified binary and development image.
4. Run the session memory, MI300X model and vfio-user ROM checks, and build the
   Rust launcher.
5. Run ``just test-rocm-regression`` with the local image and recipe identifier;
   preserve diagnostics even on failure, with distinct artifact names per recipe.

``just test-rocm-regression <output> <assets> <recipe>`` uses the Rust launcher
and the machine referenced by that recipe and creates a private disk overlay per case. It
defaults to 4 GiB of guest RAM, 4 GiB of VRAM and two guest CPUs; the 8 GiB pool
fits the hosted runner's shared-memory capacity and leaves memory for the
simulator. ``--memory``, ``--vram`` and ``--cpus`` override these
values.

The programs are ``vector_add``, ``gemm``, ``reduction``,
``transpose``, ``prefix_scan`` and ``histogram``. Each guest checks the
recipe preparation, amdgpu, KFD, render devices and the gfx942 agent reported by
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
   just test-rocm-regression <output> <assets> <recipe>

Related pages
-------------

- :doc:`workflow`
- :doc:`patch_check`
- :ref:`gs-guest-image`
- :ref:`ref-version-matrix`

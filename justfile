# SPDX-License-Identifier: Apache-2.0
#
# Task runner for cosim-gpu, the bridge that boots an AI infrastructure
# learning environment in QEMU and backs its accelerators with simulated
# GPU, NPU and TPU models (gem5 MI300X is the GPU backend).
# Run `just` to list the recipes.

set shell := ["bash", "-euo", "pipefail", "-c"]
set positional-arguments

host_arch_input := env("COSIM_HOST_ARCH", arch())
host_arch := if host_arch_input == "aarch64" { "aarch64" } else if host_arch_input == "x86_64" { "x86_64" } else { error("COSIM_HOST_ARCH must be aarch64 or x86_64") }
container_platform := if host_arch == "aarch64" { "linux/arm64" } else { "linux/amd64" }
gem5_build_dir := env("GEM5_BUILD_DIR", "build/gem5/" + host_arch + "/VEGA_X86")
rocm_recipe := "ubuntu/24.04/x86_64/rocm/7.0"
rocm_image_dir := "build/images/" + rocm_recipe
dev_image := env("COSIM_DEV_IMAGE", "cosim-dev:local")
gpu_fs_image := env("GPU_APP_BUILD_IMAGE", "ghcr.io/gem5/gpu-fs:latest")
build_jobs := env("JOBS", num_cpus())

# Recipes that use {{ dev }} run on the Host or in a temporary development
# container, as selected by COSIM_ENV.
export COSIM_ENV := env("COSIM_ENV", if os() == "linux" { "host" } else { "container" })
export COSIM_DEV_IMAGE := dev_image
export COSIM_DEV_PLATFORM := container_platform
dev := "scripts/host/dev.sh"

# List the available recipes
default:
    @just --list --unsorted

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

# Initialize the simulator and workload submodules
[group('dev')]
dev-submodules:
    git submodule update --init --recursive third_party/qemu third_party/gem5 third_party/gem5-resources

# Build the development container image
[group('dev')]
dev-image:
    docker build --platform {{ container_platform }} -t {{ dev_image }} -f scripts/host/Dockerfile.dev scripts/host

# Open a shell in a temporary development container
[group('dev')]
dev-shell:
    COSIM_ENV=container {{ dev }} --tty bash

# Build QEMU with KVM and vfio-user support
[group('build')]
build-qemu jobs=build_jobs target=host_arch:
    {{ dev }} scripts/host/build.sh qemu "$2" "$1"

# Build gem5 (VEGA_X86); use jobs=1 if linking is OOM-killed
[group('build')]
build-gem5 jobs=build_jobs *scons_args:
    {{ dev }} scripts/host/build.sh gem5 {{ gem5_build_dir }} "$@"

# Initialize gem5 sources while preserving the existing worktree
[group('dev')]
dev-gem5-source:
    if [ ! -e third_party/gem5/.git ]; then git submodule update --init third_party/gem5; fi

# Initialize gem5-resources for GPU applications and image firmware inputs
[group('dev')]
dev-rocm-sources:
    if [ ! -e third_party/gem5-resources/.git ]; then git submodule update --init third_party/gem5-resources; fi

# Build the x86 vHost OS disk image and kernel (needs Linux KVM, QEMU, ~60 GB disk)
[group('build')]
build-disk: dev-rocm-sources
    scripts/host/cosim-image build {{ rocm_recipe }}

# Build a reusable kernel/disk bundle from the vHost image recipe library
[group('build')]
build-rocm-assets recipe=rocm_recipe: dev-rocm-sources
    scripts/host/cosim-image build "$1"

# Prepare disk capacity and dependencies on a disposable CI image builder
[group('ci')]
ci-prepare-image-host:
    bash scripts/ci/prepare_image_host.sh

# Build a GPU application from third_party/gem5-resources/src/gpu
[group('build')]
build-gpu-app name="square": dev-rocm-sources
    app_src="$PWD/third_party/gem5-resources/src/gpu/$1"; \
    app_output="$PWD/build/apps/$1"; \
    test -d "$app_src"; \
    mkdir -p "$app_output"; \
    if command -v docker >/dev/null && docker info >/dev/null 2>&1; then \
        docker run --rm -u "$(id -u):$(id -g)" \
            -v "$PWD:$PWD" -w "$app_src" {{ gpu_fs_image }} \
            make -f Makefile.default "BIN_DIR=$app_output"; \
    elif command -v hipcc >/dev/null; then \
        make -C "$app_src" -f Makefile.default "BIN_DIR=$app_output"; \
    else \
        echo "Need Docker or hipcc (ROCm) to build GPU apps" >&2; \
        exit 1; \
    fi; \
    test -f "$app_output/$1.default"

# Compile the HIP test kernels under tests/ in the ROCm container
[group('build')]
build-gpu-tests:
    mkdir -p "$PWD/build/tests"
    docker run --rm -u "$(id -u):$(id -g)" \
        -v "$PWD/tests:/tests" -v "$PWD/build/tests:/build" -w /tests \
        {{ gpu_fs_image }} make BUILDDIR=/build

# Build everything needed to launch co-simulation
[group('build')]
build-all: build-qemu build-gem5 build-disk build-gpu-app build-cosim

# Build the topology launcher
[group('build')]
build-cosim:
    {{ dev }} cargo build --locked --release -p cosim-cli --bins

# Package the gem5 binary and the exact development image used to build it
[group('ci')]
ci-package-gem5 output:
    python3 scripts/ci/runtime_artifact.py package "$1" "{{ gem5_build_dir }}/gem5.opt"

# Identify the simulator source, tools, recipes and build job used by the cache
[group('ci')]
ci-gem5-key:
    python3 scripts/ci/runtime_artifact.py key

# Find a retained ROCm image from the same source repository and branch
[group('ci')]
ci-find-rocm-artifact key record:
    python3 -m scripts.ci.image_artifact find "$@"

# Publish a fully verified downloaded image into the build output directory
[group('ci')]
ci-adopt-rocm-artifact source output key:
    python3 -m scripts.ci.image_artifact adopt "$@"

# Remove only the failed download directory recorded by artifact selection
[group('ci')]
ci-discard-rocm-download record:
    python3 -m scripts.ci.image_artifact discard "$1"

# Validate the selected input identity and the complete downloaded image
[group('ci')]
ci-verify-rocm-artifact output key:
    {{ dev }} python3 -m scripts.ci.image_artifact verify "$@"

# Exercise image selection and isolation against actual published artifacts
[group('test')]
test-rocm-artifact key output:
    python3 -m scripts.ci.verify_image_artifact "$@"

# Republish a matching cached build while retaining original build provenance
[group('ci')]
ci-reuse-gem5 source output:
    python3 scripts/ci/runtime_artifact.py reuse "$@"

# Check cache invalidation, corruption rejection and original provenance
[group('test')]
test-runtime-artifact source output:
    python3 scripts/ci/verify_runtime_artifact.py "$@"

# Restore a build from the same source revision and CI run
[group('ci')]
ci-restore-gem5 source:
    python3 scripts/ci/runtime_artifact.py restore "$1" "{{ gem5_build_dir }}/gem5.opt"

# Inspect the input key or verify a locally built ROCm kernel/disk bundle
[group('ci')]
ci-rocm-assets operation *args:
    scripts/host/cosim-image "$@"

# Validate the complete image configuration with real Packer plugins
[group('check')]
check-rocm-image:
    scripts/host/cosim-image validate {{ rocm_recipe }}

# Check Packer HCL and Ansible syntax on a supported Host
[group('check')]
check-rocm-syntax:
    scripts/host/cosim-image validate {{ rocm_recipe }} --syntax-only

# Check the resource scripts used by the image producer
[group('check')]
check-rocm-build-scripts:
    shellcheck scripts/host/cosim-image resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/files/*.sh

# Exercise reuse and corruption rejection against a real built ROCm bundle
[group('test')]
test-rocm-assets output=rocm_image_dir:
    python3 -m scripts.ci.verify_rocm_assets "$1"

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

# Launch a YAML topology
[group('run')]
run-topology topology="resources/machines/single-gpu.yaml" *args:
    {{ dev }} cargo run --locked --release -q -p cosim-cli -- run "$@"

# Launch a YAML topology with the development build
[group('run')]
run-topology-dev topology="resources/machines/single-gpu.yaml" *args:
    {{ dev }} cargo run --locked -q -p cosim-cli -- run "$@"

# Inspect or operate a topology through any cosim subcommand
[group('run')]
run-cli +args:
    {{ dev }} cargo run --locked -q -p cosim-cli -- "$@"

# Launch QEMU + gem5 co-simulation (options are passed to cosim_launch.sh)
[group('run')]
run-launch *args:
    ./scripts/host/cosim_launch.sh "$@"

# Run vHost GPU tests in fresh co-simulation sessions (see run_cosim_tests.sh)
[group('test')]
test-gpu *args:
    ./scripts/host/run_cosim_tests.sh "$@"

# Run the ROCm regression suite with the built Rust launcher and verified assets
[group('test')]
test-rocm-regression output assets *args:
    {{ dev }} python3 scripts/ci/run_rocm.py "$@" --gem5 "{{ gem5_build_dir }}/gem5.opt" --qemu build/qemu/qemu-system-x86_64

# List co-simulation resources left on the Host without changing them
[group('run')]
run-preflight:
    ./scripts/host/cosim_preflight.sh

# Delete orphaned co-simulation resources (sockets, shared memory, containers)
[group('run')]
run-clean-orphans:
    ./scripts/host/cosim_launch.sh --force-clean --confirm

# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

# Check gem5 source regions, or entire explicit files, with its style tool
[group('check')]
[working-directory('third_party/gem5')]
check-gem5-style *files:
    if [ "$#" -gt 0 ]; then python3 util/style.py "$@" </dev/null; else python3 util/style.py -m $(git diff --name-only -- '*.cc' '*.hh' '*.py') </dev/null; fi

# Inspect gem5 Python formatting without modifying files
[group('check')]
[working-directory('third_party/gem5')]
check-gem5-python-format +files:
    python3 -m black --check --diff "$@"
    python3 -m isort --check-only --diff "$@"

# Inspect formatting of staged gem5 C++ changes without modifying files
[group('check')]
[working-directory('third_party/gem5')]
check-gem5-cxx-format:
    python3 util/run-git-clang-format.py --dry-run

# Run the gem5 pre-commit hooks for explicit files
[group('check')]
[working-directory('third_party/gem5')]
check-gem5-hooks +files:
    pre-commit run --files "$@"

# Validate a gem5 commit message with its repository hook
[group('check')]
[working-directory('third_party/gem5')]
check-gem5-message message:
    pre-commit run --hook-stage commit-msg --commit-msg-filename "$1"

# Validate the focused gem5 workflow
[group('check')]
check-gem5-ci:
    actionlint .github/workflows/build.yml third_party/gem5/.github/workflows/mi300x-ci.yaml

# Verify CI cancellation through the real Rust launcher and QEMU
[group('test')]
test-session-lifecycle: build-cosim
    {{ dev }} python3 -m unittest discover -s scripts/ci -p 'integration_*.py' -v

# Exercise MI300X pool ownership and its GPU_VIPER memory protocol
[group('test')]
test-gem5-mi300x output case="all":
    mkdir -p "$1"
    {{ dev }} --mount "$1" python3 third_party/gem5/tests/mi300x/verify.py --gem5 "{{ gem5_build_dir }}/gem5.opt" --output "$(cd "$1" && pwd)" --case "$2"

# Check Rust formatting, warnings and behavior
[group('check')]
check-cosim:
    {{ dev }} cargo fmt --all -- --check
    {{ dev }} cargo clippy --locked --workspace --all-targets -- -D warnings
    {{ dev }} cargo test --locked --workspace

# Inspect Rust formatting without modifying source files
[group('check')]
check-cosim-format:
    {{ dev }} cargo fmt --all -- --check

# Run the Rust tests; arguments are passed to cargo test
[group('test')]
test-cosim *args:
    {{ dev }} cargo test --locked --workspace "$@"

# Run sessions with real QEMU processes and disk images
[group('test')]
test-cosim-integration:
    {{ dev }} cargo test --locked -p cosim-cli --test sessions -- --ignored --skip vfio_user --skip bounded_memory_pool

# Verify competing sessions against a real, bounded shared-memory filesystem
[group('test')]
test-cosim-memory:
    mkdir -p build/dev-cache/memory/home build/dev-cache/memory/cargo build/tmp/memory-test
    docker run --rm --init --shm-size 96m --user "$(id -u):$(id -g)" \
        --volume "$PWD:$PWD" --workdir "$PWD" \
        --env HOME="$PWD/build/dev-cache/memory/home" \
        --env CARGO_HOME="$PWD/build/dev-cache/memory/cargo" \
        --env CARGO_TARGET_DIR="$PWD/build/cargo/container" \
        --env TMPDIR="$PWD/build/tmp/memory-test" \
        {{ dev_image }} cargo test --locked -p cosim-cli --test sessions \
        bounded_memory_pool -- --ignored --test-threads=1

# Run a vHost with a QEMU Device Model built by build-qemu
[group('test')]
test-cosim-vfio-user: dev-rocm-sources
    {{ dev }} cargo test --locked -p cosim-cli --test sessions -- --ignored vfio_user

# Run checkpatch.pl on every commit since BASE (default: merge base with origin/main)
[group('check')]
check-patch base="":
    ./scripts/host/check_patch.sh ${1:+"$1"}

# Check an uncommitted patch file before creating its signed commit
[group('check')]
check-patch-file patch:
    perl scripts/host/checkpatch.pl --no-signoff --no-tree "$1"

# Run ShellCheck on the shell scripts
[group('check')]
check-shell:
    shellcheck \
        scripts/host/*.sh \
        scripts/ci/*.sh \
        resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0/files/*.sh \
        tests/run_tests.sh tests/test_modprobe_params.sh

# Check that cosim modprobe commands carry the required amdgpu parameters
[group('check')]
check-modprobe-params:
    bash tests/test_modprobe_params.sh

# Validate MAINTAINERS.yml and require every tracked file to belong to an area
[group('check')]
check-maintainers:
    #!/usr/bin/env bash
    set -euo pipefail
    orphaned="$(python3 scripts/host/get_maintainer.py orphaned)"
    if [ -n "$orphaned" ]; then
        echo "Files not covered by any area in MAINTAINERS.yml:" >&2
        echo "$orphaned" >&2
        exit 1
    fi
    echo "MAINTAINERS.yml: valid, every tracked file belongs to an area"

# Run all Host-side checks that need no submodules or KVM
[group('check')]
check: check-patch check-shell check-maintainers check-cosim

# ---------------------------------------------------------------------------
# Maintainers
# ---------------------------------------------------------------------------

# Show the areas, maintainers and collaborators for PATHs
[group('maint')]
maint-paths +paths:
    @python3 scripts/host/get_maintainer.py path "$@"

# Show the areas touched by a commit range (default: HEAD~..)
[group('maint')]
maint-commits range="HEAD~..":
    @python3 scripts/host/get_maintainer.py commits "$1"

# List all areas with their maintainers and collaborators
[group('maint')]
maint-areas:
    @python3 scripts/host/get_maintainer.py areas

# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------

# Build the documentation site (Chinese primary, English mirror)
[group('docs')]
docs:
    docs/scripts/build.sh

# Build and serve the documentation site at http://127.0.0.1:8010/
[group('docs')]
docs-serve: docs
    docs/scripts/serve.sh

# Check RST syntax and repository documentation formatting rules
[group('docs')]
docs-format:
    docs/scripts/check_format.sh

# Check formatting, bilingual parity and the generated documentation site
[group('docs')]
docs-check: docs-format docs
    docs/scripts/check_i18n.py
    docs/scripts/verify_build.py

#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Build simulator components in the current environment.
#
# Usage: scripts/host/build.sh qemu HOST_ARCH JOBS [TARGET_ARCH]
#        scripts/host/build.sh gem5 BUILD_DIR JOBS [SCONS_ARG...]
#
# Run it through scripts/host/dev.sh to select the Host or development
# container.

set -euo pipefail

usage() {
    sed -n '4,11s/^# \{0,1\}//p' "${BASH_SOURCE[0]}"
}

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

build_qemu() {
    local arch="$1" jobs="$2" target="${3:-$1}"
    local targets="$arch-softmmu"
    case "$target" in
        x86_64 | aarch64 | riscv64) ;;
        *) echo "unsupported QEMU target: $target" >&2; return 2 ;;
    esac
    if [ "$target" != "$arch" ]; then
        targets="$targets $target-softmmu"
    fi
    local build_dir="$root/build/qemu"
    local binary="$build_dir/qemu-system-$arch"
    local device_config="$build_dir/$arch-softmmu-config-devices.mak"
    mkdir -p "$build_dir/scratch"
    export TMPDIR="$build_dir/scratch"
    if [ ! -f "$build_dir/build.ninja" ] || [ ! -f "$device_config" ] ||
        ! grep -Fqx "TARGET_DIRS=$targets" "$build_dir/config-host.mak" ||
        ! "$binary" -device help 2>/dev/null |
            grep vfio-user-pci >/dev/null ||
        { grep -qx 'CONFIG_VFIO_USER_SERVER=y' "$device_config" &&
            ! "$binary" -object help 2>/dev/null |
                grep x-vfio-user-server >/dev/null; }; then
        (
            cd "$build_dir"
            "$root/third_party/qemu/configure" \
                --target-list="${targets// /,}" --enable-kvm --enable-tcg \
                --enable-vfio-user-server --disable-docs
        )
    fi
    make -C "$build_dir" -j"$jobs"
    "$binary" -device help | grep vfio-user-pci >/dev/null
    # Foreign targets may not enable the KVM-dependent vfio-user server.
    if grep -qx 'CONFIG_VFIO_USER_SERVER=y' "$device_config"; then
        "$binary" -object help | grep x-vfio-user-server >/dev/null
    fi
    "$build_dir/qemu-system-$target" --version
    "$build_dir/qemu-img" --version
    "$build_dir/qemu-io" --version
    echo "QEMU built: $targets (build/qemu/)"
}

build_gem5() {
    local build_dir="$1" jobs="$2"
    shift 2
    case "$build_dir" in
        "$root"/build/*) ;;
        build/*) build_dir="$root/$build_dir" ;;
        *)
            echo "gem5 build directory must be under" \
                "$root/build: $build_dir" >&2
            return 2
            ;;
    esac
    case "/$build_dir/" in
        *"/../"*)
            echo "gem5 build directory must not contain" \
                "parent traversal: $build_dir" >&2
            return 2
            ;;
    esac
    cd "$root/third_party/gem5"
    mkdir -p "$build_dir/scratch"
    export TMPDIR="$build_dir/scratch"
    if [ ! -f "$build_dir/gem5.build/config" ]; then
        scons defconfig "$build_dir" build_opts/VEGA_X86
    fi
    scons "$build_dir/gem5.opt" -j"$jobs" "$@"
}

case "${1:-}" in
    qemu)
        [ "$#" -ge 3 ] && [ "$#" -le 4 ] || { usage >&2; exit 2; }
        build_qemu "$2" "$3" "${4:-$2}"
        ;;
    gem5)
        [ "$#" -ge 3 ] || { usage >&2; exit 2; }
        shift
        build_gem5 "$@"
        ;;
    -h | --help)
        usage
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac

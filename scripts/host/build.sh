#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Build simulator components in the current environment.
#
# Usage: scripts/host/build.sh qemu ARCH JOBS
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
    local arch="$1" jobs="$2"
    local build_dir="$root/build/qemu"
    local binary="$build_dir/qemu-system-$arch"
    mkdir -p "$build_dir/scratch"
    export TMPDIR="$build_dir/scratch"
    if [ ! -f "$build_dir/build.ninja" ] ||
        ! "$binary" -object help 2>/dev/null |
            grep x-vfio-user-server >/dev/null; then
        (
            cd "$build_dir"
            "$root/third_party/qemu/configure" \
                --target-list="$arch-softmmu" --enable-kvm \
                --enable-vfio-user-server --disable-docs
        )
    fi
    make -C "$build_dir" -j"$jobs"
    "$binary" -device help | grep vfio-user-pci >/dev/null
    "$binary" -object help | grep x-vfio-user-server >/dev/null
    echo "QEMU built: build/qemu/qemu-system-$arch"
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
        [ "$#" -eq 3 ] || { usage >&2; exit 2; }
        build_qemu "$2" "$3"
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

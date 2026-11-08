#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

program="$1"
test_timeout="$2"
case "$program" in
    vector_add | gemm | reduction | transpose | prefix_scan | histogram) ;;
    *) echo "Unknown ROCm regression program: $program" >&2; exit 2 ;;
esac

share="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export HSA_ENABLE_INTERRUPT=0
export TMPDIR=/root/cosim-ci/scratch
mkdir -p "$TMPDIR"
trap 'dmesg' EXIT

# shellcheck source=/dev/null
source "$share/prepare.sh"
echo "[COSIM_ENV] HSA_ENABLE_INTERRUPT=$HSA_ENABLE_INTERRUPT"
test -d /sys/module/amdgpu
test -c /dev/kfd
compgen -G '/dev/dri/renderD*' >/dev/null
timeout --kill-after=10 120 rocminfo 2>&1 | tee /root/cosim-ci/rocminfo.log
grep -Eq 'Name:[[:space:]]+gfx942([[:space:]]|$)' /root/cosim-ci/rocminfo.log
hipcc --version

cp -r "$share/kernels" "$share/common" /root/cosim-ci/
cp "$share/Makefile" /root/cosim-ci/
cd /root/cosim-ci
timeout --kill-after=10 300 make -j1 "BUILDDIR=build" "build/$program"
sha256sum "kernels/$program.cpp" "build/$program"
timeout --kill-after=10 "$test_timeout" "./build/$program"

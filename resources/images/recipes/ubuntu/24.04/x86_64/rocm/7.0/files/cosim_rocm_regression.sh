#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

program="$1"
test_timeout="$2"
case "$program" in
    vector_add | gemm | reduction | transpose | prefix_scan | histogram) ;;
    *) echo "Unknown ROCm regression program: $program" >&2; exit 2 ;;
esac

export PATH="/opt/rocm/bin:$PATH"
export LD_LIBRARY_PATH="/opt/rocm/lib:${LD_LIBRARY_PATH:-}"
export HSA_ENABLE_INTERRUPT=0
export TMPDIR=/root/cosim-ci/scratch
mkdir -p "$TMPDIR"
trap 'dmesg; journalctl -u cosim-gpu-initialize.service --no-pager' EXIT

echo "[COSIM_ENV] HSA_ENABLE_INTERRUPT=$HSA_ENABLE_INTERRUPT"
systemctl start cosim-gpu-initialize.service
systemctl is-active --quiet cosim-gpu-initialize.service
test -d /sys/module/amdgpu
test -c /dev/kfd
compgen -G '/dev/dri/renderD*' >/dev/null
for device in /sys/bus/pci/devices/*; do
    [ "$(cat "$device/vendor")" = 0x1002 ] || continue
    cat "$device/resource"
    (
        trap 'echo 0 > "$device/rom"' EXIT
        echo 1 > "$device/rom"
        cmp /root/roms/mi300.rom "$device/rom"
        sha256sum "$device/rom"
    )
done
timeout --kill-after=10 120 rocminfo 2>&1 | tee /root/cosim-ci/rocminfo.log
grep -Eq 'Name:[[:space:]]+gfx942([[:space:]]|$)' /root/cosim-ci/rocminfo.log
hipcc --version

cp -r /mnt/cosim-ci/kernels /mnt/cosim-ci/common /root/cosim-ci/
cp /mnt/cosim-ci/Makefile /root/cosim-ci/
cd /root/cosim-ci
timeout --kill-after=10 300 make -j1 "BUILDDIR=build" "build/$program"
sha256sum "kernels/$program.cpp" "build/$program"
timeout --kill-after=10 "$test_timeout" "./build/$program"

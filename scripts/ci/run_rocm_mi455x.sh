#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

program="$1"
test_timeout="$2"
export ROCM_PATH=/opt/rocm/core-10.3
export PATH="$ROCM_PATH/bin:$PATH"
export LD_LIBRARY_PATH="$ROCM_PATH/lib:$ROCM_PATH/lib/rocm_sysdeps/lib"
export HSA_ENABLE_INTERRUPT=0
unset HSA_ENABLE_SDMA
export TMPDIR=/root/cosim-ci/scratch
mkdir -p "$TMPDIR"
trap 'dmesg; journalctl -u cosim-gpu-initialize.service --no-pager' EXIT

echo "[COSIM_ENV] HSA_ENABLE_INTERRUPT=$HSA_ENABLE_INTERRUPT"
echo "[COSIM_ENV] HSA_ENABLE_SDMA=${HSA_ENABLE_SDMA:-unset}"
uname -r
systemctl start cosim-gpu-initialize.service
test -c /dev/kfd
timeout --kill-after=10 120 rocminfo 2>&1 | tee /root/cosim-ci/rocminfo.log
grep -Eq 'Name:[[:space:]]+gfx1250(-strict)?([[:space:]]|$)' \
    /root/cosim-ci/rocminfo.log
hipcc --version

cp -r /mnt/cosim-ci/kernels /mnt/cosim-ci/common /root/cosim-ci/
cp /mnt/cosim-ci/Makefile /root/cosim-ci/
cd /root/cosim-ci
timeout --kill-after=10 300 make -j1 BUILDDIR=build \
    'HIPFLAGS=--offload-arch=gfx1250-strict -O2' "build/$program"
sha256sum "kernels/$program.cpp" "build/$program"
timeout --kill-after=10 "$test_timeout" "./build/$program"

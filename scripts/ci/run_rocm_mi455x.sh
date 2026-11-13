#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

program="$1"
test_timeout="$2"
export HSA_ENABLE_INTERRUPT=0
export TMPDIR=/root/cosim-ci/scratch
mkdir -p "$TMPDIR"
# shellcheck source=/dev/null
source /mnt/cosim-ci/prepare.sh

echo "[COSIM_ENV] HSA_ENABLE_INTERRUPT=$HSA_ENABLE_INTERRUPT"
echo "[COSIM_ENV] HSA_ENABLE_SDMA=${HSA_ENABLE_SDMA:-unset}"
uname -r
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

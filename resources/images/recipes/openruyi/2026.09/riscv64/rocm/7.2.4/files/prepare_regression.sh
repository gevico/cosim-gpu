#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0

# The native openRuyi HIP compiler uses the distribution LLVM toolchain.
# shellcheck source=/dev/null
source /etc/profile.d/cosim-gpu.sh
modprobe amdgpu

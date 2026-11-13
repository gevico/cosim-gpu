#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0

export ROCM_PATH=/opt/rocm/core-10.3
export PATH="$ROCM_PATH/bin:$PATH"
export LD_LIBRARY_PATH="$ROCM_PATH/lib:$ROCM_PATH/lib/rocm_sysdeps/lib"
unset HSA_ENABLE_SDMA
trap 'dmesg; journalctl -u cosim-gpu-initialize.service --no-pager' EXIT

systemctl start cosim-gpu-initialize.service

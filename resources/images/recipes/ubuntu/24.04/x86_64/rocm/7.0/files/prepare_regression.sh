#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0

export PATH="/opt/rocm/bin:$PATH"
export LD_LIBRARY_PATH="/opt/rocm/lib:${LD_LIBRARY_PATH:-}"
trap 'dmesg; journalctl -u cosim-gpu-initialize.service --no-pager' EXIT

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

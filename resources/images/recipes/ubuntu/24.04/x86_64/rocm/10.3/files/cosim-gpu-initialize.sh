#!/bin/sh
# SPDX-License-Identifier: Apache-2.0

set -eu

modprobe amdgpu

for device in /sys/bus/pci/devices/*; do
    if [ "$(cat "$device/vendor")" = 0x1002 ] &&
       [ "$(cat "$device/device")" = 0x75c1 ] &&
       [ -L "$device/driver" ] &&
       [ "$(basename "$(readlink "$device/driver")")" = amdgpu ] &&
       [ -c /dev/kfd ]; then
        exit 0
    fi
done

echo "MI455X PCI device did not bind to amdgpu with /dev/kfd" >&2
exit 1

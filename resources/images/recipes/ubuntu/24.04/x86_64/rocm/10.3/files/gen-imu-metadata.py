#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

"""Write the IMU firmware header for the rocjitsu model."""

import argparse
from pathlib import Path
import struct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    # Linux imu_firmware_header_v1_0. The emulator has no IMU program, so
    # both microcode regions are empty.
    header = struct.Struct("<II4H8I")
    size = header.size
    args.output.write_bytes(header.pack(
        size, size, 1, 0, 12, 1, 0, 0, size, 0, 0, size, 0, size
    ))


if __name__ == "__main__":
    main()

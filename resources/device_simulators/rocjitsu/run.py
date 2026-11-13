# SPDX-License-Identifier: Apache-2.0

"""Run a rocjitsu device model selected by a device recipe."""

import argparse
import os
from pathlib import Path
import platform
import tomllib

import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--vfio-socket", required=True)
    args = parser.parse_args()

    config = args.model_config.resolve()
    document = yaml.safe_load(config.read_text())
    if document.get("version") != 1:
        parser.error("unsupported device recipe version")
    model = config.with_name(document["recipe"]["model"])
    profile_name = tomllib.loads(model.read_text())["profile"]

    workspace = Path(__file__).resolve().parents[3]
    recipe = Path(__file__).with_name("recipe.toml")
    build = tomllib.loads(recipe.read_text())["build"]
    output = workspace / "build/rocjitsu" / platform.machine() / build["config"]
    profile = (output / build["binary"]).with_name(profile_name)
    if not profile.is_file():
        parser.error(f"missing rocjitsu profile: {profile}")
    binary = os.environ.get("ROCJITSU_BINARY", str(output / build["binary"]))
    os.execvp(
        binary,
        [binary, "--config", str(profile), "--vfio-socket", args.vfio_socket],
    )


if __name__ == "__main__":
    main()

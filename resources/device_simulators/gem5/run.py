# SPDX-License-Identifier: Apache-2.0

"""Run a gem5 device model selected by a device recipe."""

import argparse
import os
from pathlib import Path
import runpy

import m5
from m5.util import addToPath
import yaml


def main():
    source = os.environ.get("GEM5_SOURCE")
    if source is None:
        source = Path(__file__).resolve().parents[3] / "third_party/gem5"
    configs = Path(source) / "configs"
    addToPath(str(configs))
    addToPath(str(configs / "example/gpufs"))

    selection = argparse.ArgumentParser(add_help=False)
    selection.add_argument("--model-config", type=Path, required=True)
    selected, _ = selection.parse_known_args()
    config = selected.model_config.resolve()
    document = yaml.safe_load(config.read_text())
    if document.get("version") != 1:
        raise ValueError("unsupported device recipe version")
    recipe = document["recipe"]
    name = recipe["model"]
    if (
        not isinstance(name, str)
        or not name
        or name in (".", "..")
        or "/" in name
        or "\\" in name
    ):
        raise ValueError("model must name a file in the device directory")
    model_path = (config.parent / name).resolve()
    if not model_path.is_relative_to(config.parent):
        raise ValueError("model escapes its device directory")
    model = runpy.run_path(str(model_path))

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-config", type=Path, required=True)
    model["add_arguments"](parser, recipe)
    args = parser.parse_args()
    root = model["build"](args)
    m5.instantiate()

    event = m5.simulate()
    while True:
        cause = event.getCause()
        if cause in (
            "m5_exit instruction encountered",
            "user interrupt received",
            "simulate() limit reached",
            "QEMU shutdown request",
            "QEMU disconnected",
        ):
            break
        if "GPU Kernel Completed" in cause:
            print(f"GPU kernel completed at tick {m5.curTick()}")
        elif "GPU Blit Kernel Completed" not in cause:
            print(f"Exit event: {cause}. Continuing...")
        event = m5.simulate(m5.MaxTick - m5.curTick())
    print(f"Exiting @ tick {m5.curTick()} because {event.getCause()}")


if __name__ == "__m5_main__":
    main()

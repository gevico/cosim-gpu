# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile

from resources.images.builder import build_recipe, inspect_recipe
from resources.images.bundle import verify_bundle
from resources.images.errors import ImageError
from resources.images.recipe import load_recipe


RECIPE = "ubuntu/24.04/x86_64/rocm/7.0"


def check(output: Path) -> None:
    workspace = Path(__file__).resolve().parents[2]
    recipe = load_recipe(workspace, RECIPE)
    state = inspect_recipe(workspace, RECIPE)
    if state["status"] != "ready":
        build_recipe(workspace, RECIPE)
    manifest = json.loads(
        (recipe.output_path(workspace) / "manifest.json").read_text()
    )
    if output.resolve() != recipe.output_path(workspace).resolve():
        raise ValueError(
            "the requested image directory must be "
            f"{recipe.output_path(workspace)}"
        )
    with tempfile.TemporaryDirectory(
        prefix="image-integrity-", dir=output.parent
    ) as name:
        directory = Path(name)
        for product in manifest["files"]:
            destination = directory / product
            if product == "kernel":
                shutil.copy2(output / product, destination)
            else:
                os.link(output / product, destination)
        shutil.copy2(output / "manifest.json", directory / "manifest.json")
        kernel = directory / "kernel"
        with kernel.open("r+b") as stream:
            stream.truncate(kernel.stat().st_size - 1)
        try:
            verify_bundle(workspace, recipe, directory, manifest["input_key"])
        except ImageError as error:
            message = str(error)
            if not any(
                reason in message
                for reason in (
                    "size mismatch: kernel",
                    "checksum mismatch: kernel",
                )
            ):
                raise
        else:
            raise AssertionError("a truncated paired kernel was accepted")
    print(json.dumps({"status": "PASS", "input_key": manifest["input_key"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check integrity gates using a real built ROCm image"
    )
    parser.add_argument("output", type=Path)
    check(parser.parse_args().output.resolve())

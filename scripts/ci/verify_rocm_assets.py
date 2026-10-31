# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import os
from pathlib import Path
import tempfile

from resources.images.bundle import verify_bundle
from resources.images.errors import ImageError
from resources.images.recipe import load_recipe


ROOT = Path(__file__).resolve().parents[2]


def check(output: Path, identifier: str) -> None:
    workspace = ROOT
    recipe = load_recipe(workspace, identifier)
    if output.resolve() != recipe.output_path(workspace).resolve():
        raise ValueError(
            "the requested image directory must be "
            f"{recipe.output_path(workspace)}"
        )
    manifest = verify_bundle(workspace, recipe, output)
    with tempfile.TemporaryDirectory(
        prefix="image-integrity-", dir=output.parent
    ) as name:
        directory = Path(name)
        for product in manifest["files"]:
            destination = directory / product
            os.link(output / product, destination)
        # Corrupt a copied manifest, never a hard-linked disk or result file.
        product = next(iter(manifest["files"]))
        manifest["files"][product]["sha256"] = "0" * 64
        (directory / "manifest.json").write_text(json.dumps(manifest) + "\n")
        try:
            verify_bundle(workspace, recipe, directory, manifest["input_key"])
        except ImageError as error:
            message = str(error)
            if f"checksum mismatch: {product}" not in message:
                raise
        else:
            raise AssertionError("an incorrect image checksum was accepted")
    print(json.dumps({"status": "PASS", "input_key": manifest["input_key"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check integrity gates using a real built ROCm image"
    )
    parser.add_argument("output", type=Path)
    parser.add_argument("--recipe", required=True)
    args = parser.parse_args()
    check(args.output.resolve(), args.recipe)

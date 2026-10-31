# SPDX-License-Identifier: Apache-2.0

from dataclasses import replace
import os
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from resources.images.bundle import (
    _stamp_matches, mark_verified_bundle, verify_bundle, write_manifest,
)
from resources.images.fingerprint import digest_json, sha256_file
from resources.images.recipe import ResultFile, load_recipe
from resources.images.toolchain import qemu_img_binary


WORKSPACE = Path(__file__).resolve().parents[2]
RECIPE_ID = "ubuntu/24.04/x86_64/rocm/7.0"


class ImageBundleVerificationStampTests(unittest.TestCase):
    def test_stamp_rejects_replaced_artifact_with_preserved_timestamp(self):
        recipe = load_recipe(WORKSPACE, RECIPE_ID)
        with tempfile.TemporaryDirectory() as name:
            temporary = Path(name)
            workspace = temporary / "workspace"
            bundle = temporary / "bundle"
            workspace.mkdir()
            bundle.mkdir()
            disk = bundle / "disk"
            disk.write_bytes(b"original image")
            inputs = {"schema": 1, "recipe": RECIPE_ID}
            manifest = {
                "schema": 1,
                "recipe": RECIPE_ID,
                "input_key": digest_json(inputs),
                "inputs": inputs,
                "disk_format": "qcow2",
                "files": {
                    "disk": {
                        "sha256": sha256_file(disk),
                        "size": disk.stat().st_size,
                    },
                },
            }
            (bundle / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            mark_verified_bundle(workspace, recipe, bundle, manifest)
            self.assertTrue(_stamp_matches(workspace, bundle, manifest))

            original_state = disk.stat()
            replacement = bundle / "replacement"
            replacement.write_bytes(b"tampered image")
            os.utime(
                replacement,
                ns=(original_state.st_atime_ns, original_state.st_mtime_ns),
            )
            replacement.replace(disk)

            self.assertFalse(_stamp_matches(workspace, bundle, manifest))


class ImageBootArtifactTests(unittest.TestCase):
    def test_bundle_accepts_elf_and_riscv_boot_images(self):
        qemu_img = qemu_img_binary(WORKSPACE)
        if qemu_img is None or shutil.which("readelf") is None:
            self.skipTest("qemu-img and readelf are required")
        header = bytearray(64)
        header[:2] = b"MZ"
        header[16:24] = (64).to_bytes(8, "little")
        header[56:60] = b"RSC\x05"
        for architecture in ["x86_64", "riscv64"]:
            with self.subTest(architecture=architecture):
                with tempfile.TemporaryDirectory() as name:
                    workspace = Path(name)
                    bundle = workspace / "bundle"
                    bundle.mkdir()
                    recipe = replace(
                        load_recipe(WORKSPACE, RECIPE_ID),
                        architecture=architecture,
                        result_files=(
                            ResultFile("kernel", "/kernel"),
                        ),
                    )
                    subprocess.run(
                        [str(qemu_img), "create", "-q", "-f", "qcow2",
                         str(bundle / "disk"), "1M"], check=True,
                    )
                    if architecture == "riscv64":
                        (bundle / "kernel").write_bytes(header)
                    else:
                        shutil.copyfile("/bin/true", bundle / "kernel")
                    inputs = {"recipe": recipe.identifier}
                    write_manifest(recipe, {
                        "inputs": inputs, "input_key": digest_json(inputs),
                    }, bundle)
                    verify_bundle(workspace, recipe, bundle)


if __name__ == "__main__":
    unittest.main()

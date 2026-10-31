# SPDX-License-Identifier: Apache-2.0

import io
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import image_artifact
import verify_rocm_assets
from image_artifact import (
    image_bundle_root, image_manifest_member, verify_image,
)
from resources.images.bundle import write_manifest
from resources.images.errors import ImageError
from resources.images.fingerprint import digest_json, sha256_file
from resources.images.recipe import load_recipe


BUILD_IMAGE_ROOT = "build/images/ubuntu/24.04/x86_64/rocm/7.0"
IMAGE_ROOT = "images/ubuntu/24.04/x86_64/rocm/7.0"
RECIPE_ID = "ubuntu/24.04/x86_64/rocm/7.0"


class ImageManifestMemberTests(unittest.TestCase):
    def archive_with(self, path: str) -> zipfile.ZipFile:
        content = io.BytesIO()
        with zipfile.ZipFile(content, "w") as archive:
            archive.writestr(path, "{}")
        return zipfile.ZipFile(io.BytesIO(content.getvalue()))

    def test_finds_manifest_in_build_rooted_diagnostic_artifact(self):
        path = f"{BUILD_IMAGE_ROOT}/manifest.json"
        with self.archive_with(path) as archive:
            member = image_manifest_member(archive, RECIPE_ID)
        self.assertIsNotNone(member)
        self.assertEqual(member.filename, path)

    def test_finds_manifest_in_existing_diagnostic_artifact(self):
        path = f"{IMAGE_ROOT}/manifest.json"
        with self.archive_with(path) as archive:
            member = image_manifest_member(archive, RECIPE_ID)
        self.assertIsNotNone(member)
        self.assertEqual(member.filename, path)

    def test_finds_manifest_at_the_artifact_root(self):
        with self.archive_with("manifest.json") as archive:
            member = image_manifest_member(archive, RECIPE_ID)
        self.assertIsNotNone(member)
        self.assertEqual(member.filename, "manifest.json")

    def test_missing_manifest_is_ignored(self):
        with self.archive_with(f"{BUILD_IMAGE_ROOT}/build.log") as archive:
            self.assertIsNone(image_manifest_member(archive, RECIPE_ID))

    def test_finds_only_the_requested_recipe_manifest(self):
        recipe = "debian/13/x86_64/rocm/7.1"
        path = f"build/images/{recipe}/manifest.json"
        with self.archive_with(path) as archive:
            member = image_manifest_member(archive, recipe)
            self.assertEqual(member.filename,
                             f"build/images/{recipe}/manifest.json")
            self.assertIsNone(image_manifest_member(archive, RECIPE_ID))


@unittest.skipUnless(shutil.which("qemu-img"), "requires qemu-img")
class RecipeArtifactVerificationTests(unittest.TestCase):
    def test_disk_only_recipe_verification_preserves_original_artifacts(self):
        recipe_id = "debian/13/x86_64/rocm/7.1"
        source = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as name:
            workspace = Path(name)
            directory = workspace / "resources/images/recipes" / recipe_id
            shutil.copytree(source / "resources/images/recipes" / RECIPE_ID,
                            directory)
            metadata = directory / "recipe.toml"
            metadata.write_text(metadata.read_text().split("[result]")[0]
                                + "[result]\n")
            recipe = load_recipe(workspace, recipe_id)
            output = recipe.output_path(workspace)
            output.mkdir(parents=True)
            subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2",
                            str(output / "disk"), "1M"], check=True)
            inputs = {"recipe": recipe_id}
            key = digest_json(inputs)
            write_manifest(recipe, {"inputs": inputs, "input_key": key}, output)
            original = sha256_file(output / "disk")
            manifest = (output / "manifest.json").read_bytes()
            with patch.object(image_artifact, "ROOT", workspace):
                self.assertEqual(
                    verify_image(output, key, recipe_id)[0], output
                )
                with self.assertRaises(ImageError):
                    verify_image(output, "different-key", recipe_id)
            with patch.object(verify_rocm_assets, "ROOT", workspace):
                verify_rocm_assets.check(output, recipe_id)
            self.assertEqual(sha256_file(output / "disk"), original)
            self.assertEqual((output / "manifest.json").read_bytes(), manifest)


class ImageBundleRootTests(unittest.TestCase):
    def test_uses_manifest_at_download_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            download = Path(temporary)
            (download / "manifest.json").write_text("{}\n")

            self.assertEqual(image_bundle_root(download), download)

    def test_finds_manifest_in_nested_download_layout(self):
        with tempfile.TemporaryDirectory() as temporary:
            download = Path(temporary)
            bundle = download / "rocm-guest-38995128420-1"
            bundle.mkdir()
            (bundle / "manifest.json").write_text("{}\n")

            self.assertEqual(image_bundle_root(download), bundle)

    def test_rejects_ambiguous_nested_manifests(self):
        with tempfile.TemporaryDirectory() as temporary:
            download = Path(temporary)
            first = download / "first"
            second = download / "second"
            first.mkdir()
            second.mkdir()
            (first / "manifest.json").write_text("{}\n")
            (second / "manifest.json").write_text("{}\n")

            with self.assertRaisesRegex(
                ValueError, "expected one ROCm artifact manifest"
            ):
                image_bundle_root(download)

# SPDX-License-Identifier: Apache-2.0

import io
import json
import os
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
    Scope, find_image, image_bundle_root, image_manifest_member, verify_image,
)
from ci_lifecycle import Lifecycle
from resources.images.bundle import write_manifest
from resources.images.errors import ImageError
from resources.images.fingerprint import digest_json, sha256_file
from resources.images.recipe import load_recipe


BUILD_IMAGE_ROOT = "build/images/ubuntu/24.04/x86_64/rocm/7.0"
IMAGE_ROOT = "images/ubuntu/24.04/x86_64/rocm/7.0"
RECIPE_ID = "ubuntu/24.04/x86_64/rocm/7.0"


class HistoricalImageReuseTests(unittest.TestCase):
    def records(self, **scope_changes):
        scope = {"id": 10, "head_repository_id": 7, "head_branch": "topic",
                 **scope_changes}
        return [
            {"id": 31, "name": "rocm-guest-tag-10-1", "expired": False,
             "workflow_run": scope},
            {"id": 32, "name": "rocm-image-logs-tag-10-1", "expired": False,
             "size_in_bytes": 1024, "workflow_run": scope},
        ]

    def test_later_ci_run_selects_the_earlier_matching_image(self):
        inputs = {"recipe": RECIPE_ID, "files": {"provision.yml": "fixture"}}
        key = digest_json(inputs)
        content = io.BytesIO()
        with zipfile.ZipFile(content, "w") as archive:
            archive.writestr("manifest.json", json.dumps({
                "schema": 1, "recipe": RECIPE_ID, "inputs": inputs,
                "input_key": key,
            }))
        with patch.dict(os.environ, GITHUB_RUN_ID="11"), patch.object(
            image_artifact, "github", side_effect=[
                json.dumps([{"artifacts": self.records()}]).encode(),
                content.getvalue(),
            ],
        ):
            result = find_image(key, Scope("owner/repo", 7, "topic"),
                                Lifecycle(), RECIPE_ID)
        self.assertIsNotNone(result)
        self.assertEqual(result.run_id, 10)
        self.assertEqual(result.artifact_id, 31)

    def test_history_lookup_preserves_source_and_expiry_isolation(self):
        for records in (self.records(head_branch="another"),
                        self.records(head_repository_id=8), [
                            {**record, "expired": True}
                            for record in self.records()
                        ]):
            with self.subTest(records=records), patch.object(
                image_artifact, "github",
                return_value=json.dumps([{"artifacts": records}]).encode(),
            ) as api:
                self.assertIsNone(find_image(
                    "unused-key", Scope("owner/repo", 7, "topic"),
                    Lifecycle(), RECIPE_ID,
                ))
                self.assertEqual(api.call_count, 1)


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


class RecipeArtifactVerificationTests(unittest.TestCase):
    def test_disk_only_recipe_verification_preserves_original_artifacts(self):
        recipe_id = "debian/13/x86_64/rocm/7.1"
        source = Path(__file__).resolve().parents[2]
        qemu_img = source / "build/qemu/qemu-img"
        self.assertTrue(qemu_img.is_file(), "run just build-qemu")
        with tempfile.TemporaryDirectory() as name:
            workspace = Path(name)
            helper = workspace / "build/qemu/qemu-img"
            helper.parent.mkdir(parents=True)
            helper.symlink_to(qemu_img)
            directory = workspace / "resources/images/recipes" / recipe_id
            shutil.copytree(source / "resources/images/recipes" / RECIPE_ID,
                            directory)
            metadata = directory / "recipe.toml"
            metadata.write_text(metadata.read_text().split("[result]")[0]
                                + "[result]\n")
            recipe = load_recipe(workspace, recipe_id)
            output = recipe.output_path(workspace)
            output.mkdir(parents=True)
            subprocess.run([helper, "create", "-q", "-f", "qcow2",
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

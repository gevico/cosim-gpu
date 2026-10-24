# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import runtime_artifact


RECIPE = "resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0"


@unittest.skipUnless(shutil.which("just"), "requires just")
class Gem5BuildKeyTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for name in (
            "justfile", ".github/workflows/build.yml", ".gitmodules",
            "scripts/host/build.sh", "scripts/host/dev.sh",
            "scripts/host/Dockerfile.dev", "scripts/ci/runtime_artifact.py",
            f"{RECIPE}/recipe.toml", f"{RECIPE}/provision.yml",
            "resources/vhosts/qemu.yaml",
        ):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(runtime_artifact.ROOT / name, destination)
        self.identity = {"project": "project-a", "gem5": "gem5-a"}
        self.enterContext(patch.object(runtime_artifact, "ROOT", self.root))
        self.enterContext(patch.object(
            runtime_artifact, "source_identity", return_value=self.identity
        ))
        self.enterContext(patch.dict(os.environ, {
            "COSIM_ENV": "container", "COSIM_DEV_IMAGE": "cosim-dev:ci",
        }))

    @contextmanager
    def changed(self, name, contents):
        path = self.root / name
        original = path.read_text()
        self.assertNotEqual(original, contents)
        path.write_text(contents)
        try:
            yield
        finally:
            path.write_text(original)

    def test_vhost_just_settings_keep_the_gem5_key(self):
        original_key = runtime_artifact.build_key()
        original = (self.root / "justfile").read_text()
        changes = {
            "recipe": original.replace(
                'rocm_recipe := "ubuntu/24.04/x86_64/rocm/7.0"',
                'rocm_recipe := "ubuntu/26.04/x86_64/rocm/8.0"',
            ),
            "output": original.replace(
                'rocm_image_dir := "build/images/"',
                'rocm_image_dir := "build/other-images/"',
            ),
            "additional vhost setting": original +
            '\nvhost_image_variant := "another-image"\n',
        }
        for label, contents in changes.items():
            with self.subTest(change=label):
                with self.changed("justfile", contents):
                    self.assertEqual(original_key, runtime_artifact.build_key())

    def test_vhost_source_changes_keep_the_gem5_key(self):
        original_key = runtime_artifact.build_key()
        for name, before, after in (
            (f"{RECIPE}/recipe.toml", "6.8.0-124-generic", "6.8.0-125-generic"),
            (f"{RECIPE}/provision.yml", "- vim", "- nano"),
            ("resources/vhosts/qemu.yaml", "memory: 8G", "memory: 16G"),
        ):
            with self.subTest(file=name):
                original = (self.root / name).read_text()
                with self.changed(name, original.replace(before, after)):
                    self.identity["project"] = "project-with-vhost-change"
                    self.assertEqual(original_key, runtime_artifact.build_key())

    def test_gem5_build_inputs_still_invalidate_the_key(self):
        original_key = runtime_artifact.build_key()
        self.identity["gem5"] = "gem5-b"
        self.assertNotEqual(original_key, runtime_artifact.build_key())
        self.identity["gem5"] = "gem5-a"
        for name, before, after in (
            ("justfile", '"/VEGA_X86"', '"/OTHER_TARGET"'),
            ("justfile", 'dev := "scripts/host/dev.sh"',
             'dev := "scripts/host/other-dev.sh"'),
            (
                ".github/workflows/build.yml",
                "GOLD_LINKER=True", "GOLD_LINKER=False",
            ),
        ):
            with self.subTest(file=name):
                original = (self.root / name).read_text()
                with self.changed(name, original.replace(before, after)):
                    self.assertNotEqual(
                        original_key, runtime_artifact.build_key()
                    )


if __name__ == "__main__":
    unittest.main()

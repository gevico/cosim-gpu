# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from resources.images.fingerprint import sha256_file
from resources.images.identity import (
    _input_candidates,
    recipe_source_files,
    reusable_input_issues,
    stage_recipe,
)
from resources.images.recipe import load_recipe
from resources.images.toolchain import ANSIBLE_CORE_VERSION, PACKER_VERSION


WORKSPACE = Path(__file__).resolve().parents[2]
RECIPE_ID = "ubuntu/24.04/x86_64/rocm/7.0"


class ReusableImageInputTests(unittest.TestCase):
    def test_recipe_sources_exclude_deleted_worktree_files(self):
        source_recipe = load_recipe(WORKSPACE, RECIPE_ID)
        with tempfile.TemporaryDirectory() as name:
            workspace = Path(name)
            relative_recipe = Path("resources/images/recipes") / RECIPE_ID
            recipe_directory = workspace / relative_recipe
            recipe_directory.parent.mkdir(parents=True)
            shutil.copytree(source_recipe.directory, recipe_directory)
            deleted = recipe_directory / "deleted-input.txt"
            deleted.write_text("tracked then deleted\n", encoding="utf-8")
            subprocess.run(
                ["git", "init", "--quiet"], cwd=workspace, check=True
            )
            subprocess.run(
                ["git", "add", str(relative_recipe)],
                cwd=workspace,
                check=True,
            )
            deleted.unlink()
            recipe = load_recipe(workspace, RECIPE_ID)

            sources = recipe_source_files(workspace, recipe)

            self.assertTrue(sources)
            self.assertNotIn(deleted, [path for _, path in sources])
            for _, path in sources:
                self.assertTrue(
                    path.is_file(), f"missing recipe source: {path}"
                )

    def test_untracked_recipe_files_are_staged_but_ignored_files_are_not(self):
        source_recipe = load_recipe(WORKSPACE, RECIPE_ID)
        with tempfile.TemporaryDirectory() as name:
            workspace = Path(name)
            relative_recipe = Path("resources/images/recipes") / RECIPE_ID
            recipe_directory = workspace / relative_recipe
            recipe_directory.parent.mkdir(parents=True)
            shutil.copytree(source_recipe.directory, recipe_directory)
            (recipe_directory / ".gitignore").write_text(
                "ignored-input.txt\n", encoding="utf-8"
            )
            subprocess.run(
                ["git", "init", "--quiet"], cwd=workspace, check=True
            )
            subprocess.run(
                ["git", "add", str(relative_recipe)],
                cwd=workspace,
                check=True,
            )
            untracked = recipe_directory / "local-input.txt"
            untracked.write_text("untracked input\n", encoding="utf-8")
            (recipe_directory / "ignored-input.txt").write_text(
                "ignored input\n", encoding="utf-8"
            )

            recipe = load_recipe(workspace, RECIPE_ID)
            paths = {
                relative
                for relative, _ in recipe_source_files(workspace, recipe)
            }

            self.assertIn(untracked.relative_to(workspace).as_posix(), paths)
            self.assertNotIn(
                (recipe_directory / "ignored-input.txt")
                .relative_to(workspace)
                .as_posix(),
                paths,
            )
            staged = stage_recipe(
                workspace, recipe, workspace / "build/staging"
            )

            self.assertTrue(
                (staged.directory / "local-input.txt").is_file()
            )
            self.assertFalse(
                (staged.directory / "ignored-input.txt").exists()
            )
            self.assertTrue(staged.playbook_file.is_file())
            self.assertEqual(
                staged.provision_files["mi300_rom"],
                recipe.provision_files["mi300_rom"],
            )

    def test_removed_recipe_file_invalidates_a_previous_bundle(self):
        recipe = load_recipe(WORKSPACE, RECIPE_ID)
        files = {}
        for _, path in _input_candidates(WORKSPACE, recipe):
            resolved = path.resolve()
            if resolved.is_file():
                files[resolved.relative_to(WORKSPACE).as_posix()] = (
                    sha256_file(resolved)
                )
        stored = {
            "schema": 1,
            "recipe": recipe.identifier,
            "base": {
                "url": recipe.base_url,
                "sha256": recipe.base_sha256,
                "format": recipe.base_format,
            },
            "epoch": os.environ.get("COSIM_ROCM_IMAGE_EPOCH", "1"),
            "toolchain": {
                "packer": PACKER_VERSION,
                "ansible_core": ANSIBLE_CORE_VERSION,
            },
            "files": files,
        }
        baseline_issues = reusable_input_issues(WORKSPACE, recipe, stored)

        removed_path = "resources/images/packer/removed-template.pkr.hcl"
        stored["files"][removed_path] = "0" * 64

        issues = reusable_input_issues(WORKSPACE, recipe, stored)
        self.assertEqual(
            issues,
            [*baseline_issues, f"image input removed: {removed_path}"],
        )


if __name__ == "__main__":
    unittest.main()

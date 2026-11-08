# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from resources.images.fingerprint import sha256_file
from resources.images.identity import (
    _input_candidates,
    input_fingerprint,
    recipe_source_files,
    reusable_input_issues,
    stage_recipe,
)
from resources.images.recipe import load_recipe
from resources.images.toolchain import (
    ANSIBLE_CORE_VERSION, PACKER_VERSION, Toolchain,
)


WORKSPACE = Path(__file__).resolve().parents[2]
RECIPE_ID = "ubuntu/24.04/x86_64/rocm/7.0"


class ReusableImageInputTests(unittest.TestCase):
    def test_cmodel_commits_and_ci_runs_preserve_the_image_key(self):
        source_recipe = load_recipe(WORKSPACE, RECIPE_ID)
        with tempfile.TemporaryDirectory() as name:
            workspace = Path(name)
            target = workspace / "resources/images/recipes" / RECIPE_ID
            target.parent.mkdir(parents=True)
            shutil.copytree(source_recipe.directory, target)
            shutil.copytree(WORKSPACE / "resources/images/packer",
                            workspace / "resources/images/packer")
            subprocess.run(
                ["git", "init", "--quiet"], cwd=workspace, check=True
            )
            recipe = load_recipe(workspace, RECIPE_ID)
            for _, path in _input_candidates(workspace, recipe):
                if path.exists():
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                source = WORKSPACE / path.relative_to(workspace)
                if source.is_file():
                    shutil.copyfile(source, path)
                else:
                    # Firmware bytes are fixtures for the input-key contract.
                    path.write_bytes(b"fixture firmware")
            cmodel = workspace / "third_party/gem5/src/gpu-compute/model.cc"
            cmodel.parent.mkdir(parents=True)
            cmodel.write_text("model version 1\n")
            subprocess.run(["git", "add", "."], cwd=workspace, check=True)
            commit = ["git", "-c", "user.name=Fixture", "-c",
                      "user.email=fixture@example.invalid", "commit", "--quiet"]
            subprocess.run([*commit, "-m", "initial inputs"],
                           cwd=workspace, check=True)
            old_head = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=workspace, text=True
            ).strip()
            tools = Toolchain(
                workspace / "qemu", "x86_64", workspace / "qemu-img",
                "fixture QEMU", "0" * 64, "fixture qemu-img", "1" * 64,
            )
            with patch.dict(os.environ, {
                "GITHUB_RUN_ID": "10", "GITHUB_SHA": old_head,
            }):
                first = input_fingerprint(workspace, recipe, tools)
            cmodel.write_text("model version 2\n")
            subprocess.run([*commit, "-am", "change only CModel"],
                           cwd=workspace, check=True)
            new_head = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=workspace, text=True
            ).strip()
            self.assertNotEqual(old_head, new_head)
            with patch.dict(os.environ, {
                "GITHUB_RUN_ID": "11", "GITHUB_SHA": new_head,
            }):
                second = input_fingerprint(workspace, recipe, tools)
            self.assertEqual(first["input_key"], second["input_key"])
            with recipe.playbook_file.open("a") as source:
                source.write("\n# changed image provisioning\n")
            self.assertNotEqual(
                second["input_key"],
                input_fingerprint(workspace, recipe, tools)["input_key"],
            )

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

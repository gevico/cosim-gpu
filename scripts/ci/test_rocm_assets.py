# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
import shutil
import tempfile
import tomllib
import unittest

from resources.images.recipe import RecipeError, list_recipes, load_recipe


WORKSPACE = Path(__file__).resolve().parents[2]
RECIPE = "ubuntu/24.04/x86_64/rocm/7.0"


class ImageRecipeTests(unittest.TestCase):
    def test_recipe_identity_comes_from_its_directory(self):
        self.assertIn(RECIPE, list_recipes(WORKSPACE))
        recipe = load_recipe(WORKSPACE, RECIPE)
        self.assertEqual(recipe.distribution, "ubuntu")
        self.assertEqual(recipe.release, "24.04")
        self.assertEqual(recipe.architecture, "x86_64")
        self.assertEqual(recipe.software, "rocm")
        self.assertEqual(recipe.software_release, "7.0")
        self.assertEqual(len(recipe.base_sha256), 64)
        self.assertEqual(recipe.kernel_file, "kernel")

        metadata = tomllib.loads(
            recipe.recipe_file.read_text(encoding="utf-8")
        )
        for duplicate in (
            "id", "role", "distribution", "release", "architecture",
        ):
            with self.subTest(duplicate=duplicate):
                self.assertNotIn(duplicate, metadata)
        self.assertNotIn("rocm_release", metadata["provision"]["variables"])

    def test_recipe_outputs_and_sources_stay_in_the_workspace(self):
        recipe = load_recipe(WORKSPACE, RECIPE)
        self.assertTrue(
            recipe.output_path(WORKSPACE).is_relative_to(WORKSPACE)
        )
        self.assertTrue(recipe.playbook_file.is_relative_to(WORKSPACE))
        for path in recipe.provision_files.values():
            self.assertTrue(path.is_relative_to(WORKSPACE))

    def test_recipe_uses_one_ansible_playbook(self):
        recipe = load_recipe(WORKSPACE, RECIPE)
        self.assertEqual(recipe.playbook_file.name, "provision.yml")
        self.assertFalse((recipe.directory / "tasks.yml").exists())
        playbook = recipe.playbook_file.read_text(encoding="utf-8")
        self.assertIn("  tasks:\n", playbook)
        self.assertIn("Fetch declared result files", playbook)

    def test_recipe_has_no_standalone_gem5_guest_inputs(self):
        recipe = load_recipe(WORKSPACE, RECIPE)
        standalone_inputs = {
            "m5",
            "run_gem5_app",
            "load_amdgpu",
            "gem5_wmi_source",
            "gem5_wmi_makefile",
            "amd_bsd_license",
        }
        self.assertTrue(standalone_inputs.isdisjoint(recipe.provision_files))

    def test_recipe_image_inputs_are_present_at_declared_paths(self):
        recipe = load_recipe(WORKSPACE, RECIPE)
        external_firmware_inputs = {
            "mi200_rom": "mi200.rom",
            "mi300_rom": "mi300.rom",
            "mi300_discovery": "mi300_discovery",
            "mi350_discovery": "mi350_discovery",
        }
        self.assertLessEqual(
            external_firmware_inputs.keys(), recipe.provision_files.keys()
        )
        for name, path in recipe.provision_files.items():
            with self.subTest(input_name=name):
                if name in external_firmware_inputs:
                    expected = (
                        WORKSPACE
                        / "third_party/gem5-resources/src/x86-ubuntu-gpu-ml"
                        / "files"
                        / external_firmware_inputs[name]
                    )
                    self.assertEqual(path, expected)
                    submodule_metadata = (
                        WORKSPACE / "third_party/gem5-resources/.git"
                    )
                    if not path.is_file() and not submodule_metadata.exists():
                        # The fast CI job checks out no submodules.
                        continue
                else:
                    self.assertTrue(
                        path.resolve().is_relative_to(recipe.directory),
                        f"image input is outside its recipe: {path}",
                    )
                self.assertTrue(path.is_file(), f"missing image input: {path}")

    def test_recipe_identifier_rejects_parent_traversal(self):
        with self.assertRaises(RecipeError):
            load_recipe(WORKSPACE, "../../outside")

    def test_recipe_identifier_requires_the_five_level_hierarchy(self):
        recipe = load_recipe(WORKSPACE, RECIPE)
        with tempfile.TemporaryDirectory() as name:
            workspace = Path(name)
            recipe_directory = (
                workspace / "resources/images/recipes/ubuntu/24.04/x86_64/rocm"
            )
            recipe_directory.parent.mkdir(parents=True)
            shutil.copytree(recipe.directory, recipe_directory)

            with self.assertRaisesRegex(
                RecipeError, "five path components"
            ):
                load_recipe(workspace, "ubuntu/24.04/x86_64/rocm")

    def test_result_kernel_must_name_a_declared_result_file(self):
        recipe = load_recipe(WORKSPACE, RECIPE)
        with tempfile.TemporaryDirectory() as name:
            workspace = Path(name)
            recipe_directory = (
                workspace / "resources/images/recipes" / RECIPE
            )
            recipe_directory.parent.mkdir(parents=True)
            shutil.copytree(recipe.directory, recipe_directory)
            recipe_file = recipe_directory / "recipe.toml"
            content = recipe_file.read_text(encoding="utf-8")
            current = '[result]\nkernel = "kernel"'
            mismatch = '[result]\nkernel = "missing"'
            self.assertIn(current, content)
            recipe_file.write_text(
                content.replace(current, mismatch, 1), encoding="utf-8"
            )

            with self.assertRaisesRegex(
                RecipeError,
                "result.kernel must name a declared result file",
            ):
                load_recipe(workspace, RECIPE)

    def test_bundle_metadata_names_cannot_be_provisioning_outputs(self):
        recipe = load_recipe(WORKSPACE, RECIPE)
        reserved_names = ("disk", "manifest.json", "packer.log", "build.log")
        for reserved_name in reserved_names:
            with self.subTest(output_name=reserved_name):
                with tempfile.TemporaryDirectory() as name:
                    workspace = Path(name)
                    recipe_directory = (
                        workspace / "resources/images/recipes" / RECIPE
                    )
                    recipe_directory.parent.mkdir(parents=True)
                    shutil.copytree(recipe.directory, recipe_directory)
                    recipe_file = recipe_directory / "recipe.toml"
                    content = recipe_file.read_text(encoding="utf-8")
                    content = content.replace(
                        'name = "kernel"',
                        f'name = "{reserved_name}"',
                        1,
                    )
                    recipe_file.write_text(content, encoding="utf-8")

                    with self.assertRaisesRegex(RecipeError, "is reserved"):
                        load_recipe(workspace, RECIPE)


if __name__ == "__main__":
    unittest.main()

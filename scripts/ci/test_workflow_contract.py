# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from contextlib import redirect_stdout
import io
import json
import os
import unittest
from unittest.mock import patch

import yaml

from wait_gem5 import PRODUCER


ROOT = Path(__file__).resolve().parents[2]


def workflow(name):
    return yaml.load(
        (ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader
    )


class ImageRegressionWorkflowTests(unittest.TestCase):
    ubuntu = "ubuntu/24.04/x86_64/rocm/7.0"
    openruyi = "openruyi/2026.09/riscv64/rocm/7.2.4"

    def plan(self, paths=(), requested="", base="base"):
        planner = workflow("build.yml")["jobs"]["changes"]["steps"][-1]["run"]
        source = planner.split('PYCODE\' >> "$GITHUB_OUTPUT"\n', 1)[1]
        source = source.rsplit("PYCODE", 1)[0]
        output = io.StringIO()
        with patch.dict(os.environ, {
            "CI_BASE": base, "CI_RECIPE": requested,
        }), patch("subprocess.check_output", return_value=(
            b"\0".join(path.encode() for path in paths) + b"\0"
        )), redirect_stdout(output):
            exec(compile(source, "workflow planner", "exec"), {})
        result = dict(line.split("=", 1)
                      for line in output.getvalue().splitlines())
        return json.loads(result["regression"]), json.loads(result["recipes"])

    def test_recipe_changes_require_hip_for_the_selected_recipe(self):
        for recipe in (self.ubuntu, self.openruyi):
            with self.subTest(recipe=recipe):
                required, selected = self.plan([
                    f"resources/images/recipes/{recipe}/recipe.toml",
                    "docs/zh/contributing/ci.rst",
                ])
                self.assertTrue(required)
                self.assertEqual(selected, [recipe])

    def test_manual_recipe_selection_requires_hip(self):
        for recipe in (self.ubuntu, self.openruyi):
            with self.subTest(recipe=recipe):
                required, selected = self.plan(requested=recipe)
                self.assertTrue(required)
                self.assertEqual(selected, [recipe])

    def test_shared_and_removed_recipe_paths_check_every_recipe_once(self):
        for path in (
            ".github/workflows/build.yml",
            "resources/images/recipes/removed/1/x86_64/rocm/1/recipe.toml",
        ):
            with self.subTest(path=path):
                required, selected = self.plan([path])
                self.assertTrue(required)
                self.assertEqual(selected, sorted([self.ubuntu, self.openruyi]))

    def test_documentation_changes_skip_heavy_checks(self):
        self.assertEqual(
            self.plan(["docs/zh/contributing/ci.rst"]), (False, [])
        )

    def test_manual_full_run_checks_every_recipe_once(self):
        self.assertEqual(self.plan(base=""), (
            True, sorted([self.ubuntu, self.openruyi]),
        ))

    def test_multiple_recipe_paths_do_not_duplicate_regression_jobs(self):
        required, selected = self.plan([
            f"resources/images/recipes/{self.ubuntu}/recipe.toml",
            f"resources/images/recipes/{self.ubuntu}/provision.yml",
            f"resources/images/recipes/{self.openruyi}/recipe.toml",
        ])
        self.assertTrue(required)
        self.assertEqual(selected, sorted([self.ubuntu, self.openruyi]))

    def test_missing_profile_fails_instead_of_skipping_hip(self):
        recipe = "example/1/riscv64/rocm/1"
        with patch(
            "resources.images.recipe.list_recipes", return_value=[recipe],
        ):
            with self.assertRaisesRegex(ValueError, "regression.toml"):
                self.plan(requested=recipe)

    def test_unknown_manual_recipe_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown recipe"):
            self.plan(requested="unknown/1/riscv64/rocm/1")

    def test_image_preparation_can_start_while_gem5_builds(self):
        jobs = workflow("build.yml")["jobs"]
        recipes = jobs["recipes"]
        self.assertEqual(recipes["uses"], "./.github/workflows/image.yml")
        self.assertEqual(recipes["needs"], "changes")
        self.assertEqual(recipes["with"], {"recipe": "${{ matrix.recipe }}"})
        self.assertNotIn("rocm", jobs)
        self.assertIn("recipes", jobs["regression"]["needs"])
        self.assertEqual(jobs["build-gem5"]["name"], PRODUCER)
        publication = next(step for step in jobs["build-gem5"]["steps"]
                           if step.get("id") == "runtime")
        self.assertEqual(
            publication["with"]["name"],
            "gem5-runtime-${{ github.run_id }}-${{ github.run_attempt }}",
        )

    def test_regression_consumes_the_verified_image_in_the_same_job(self):
        image = workflow("image.yml")["jobs"]["image"]
        steps = image["steps"]
        commands = [(i, step) for i, step in enumerate(steps) if "run" in step]

        def command(fragment):
            return next((i, step) for i, step in commands
                        if fragment in step["run"])

        built, _ = command("just build-rocm-assets")
        verified, _ = command("just test-rocm-assets")
        synchronized, barrier = command("just ci-wait-gem5")
        restored, restore = command("just ci-restore-gem5")
        tested, tests = command("just test-gem5-mi300x")
        executed, regression = command("just test-rocm-regression")
        self.assertLess(built, verified)
        self.assertLess(verified, synchronized)
        self.assertLess(synchronized, restored)
        self.assertLess(restored, tested)
        self.assertLess(tested, executed)
        for step in (barrier, restore, tests, regression):
            self.assertNotIn("if", step)
        for step in (tests, regression):
            self.assertEqual(step["env"]["COSIM_ENV"], "container")
        self.assertEqual(
            regression["env"]["IMAGE_DIRECTORY"],
            "${{ steps.recipe.outputs.directory }}",
        )
        self.assertIn('"$IMAGE_DIRECTORY"', regression["run"])
        runtime = next(step for step in steps
                       if step.get("with", {}).get("artifact-ids")
                       == "${{ steps.gem5.outputs.artifact-id }}")
        self.assertNotIn("if", runtime)
        self.assertNotIn("guest-artifact", str(steps))
        evidence = next(
            step for step in steps
            if step.get("name") == "Upload complete regression evidence"
        )
        self.assertIn("always()", evidence["if"])

    def test_image_workflow_has_no_optional_hip_mode(self):
        inputs = workflow("image.yml")["on"]["workflow_call"]["inputs"]
        self.assertEqual(set(inputs), {"recipe"})


if __name__ == "__main__":
    unittest.main()

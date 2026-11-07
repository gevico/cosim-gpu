# SPDX-License-Identifier: Apache-2.0

from contextlib import redirect_stdout
import io
from pathlib import Path
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

import yaml

from resources.device_simulators.recipe import load_recipe

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "resources/device_simulators/gem5/run.py"


class SimulatorRecipeTests(unittest.TestCase):
    def test_gem5_recipe_selects_a_build_and_entry(self):
        recipe = load_recipe(ROOT, "gem5")
        self.assertEqual(recipe.source, ROOT / "third_party/gem5")
        self.assertEqual(recipe.config, "VEGA_X86")
        self.assertEqual(recipe.binary, "gem5.opt")
        self.assertEqual(
            recipe.output("aarch64"), "build/gem5/aarch64/VEGA_X86"
        )
        self.assertEqual(recipe.entry, RUNNER)

    def test_invalid_identifiers_and_build_paths_fail(self):
        for name in ("../gem5", "/gem5", "gem5/VEGA_X86", "gem5/../x"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                load_recipe(ROOT, name)
        recipe = load_recipe(ROOT, "gem5")
        for name in (
            "/tmp/output", "build/../output", "third_party/gem5/build",
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                recipe.build_directory(name)

    def test_unknown_fields_and_escaping_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            target = workspace / "resources/device_simulators/gem5"
            target.mkdir(parents=True)
            source = ROOT / "resources/device_simulators/gem5/recipe.toml"
            for text in (
                source.read_text() + '\nunknown = "value"\n',
                source.read_text().replace("third_party/gem5", "../outside"),
            ):
                (target / "recipe.toml").write_text(text)
                with self.subTest(text=text), self.assertRaises(ValueError):
                    load_recipe(workspace, "gem5")

    def test_runner_finds_native_and_container_configuration_libraries(self):
        class ConfigurationPath(Exception):
            pass

        utility = ModuleType("m5.util")

        def add_to_path(path):
            raise ConfigurationPath(path)

        utility.addToPath = add_to_path
        modules = {"m5": ModuleType("m5"), "m5.util": utility}
        for source, script_path, expected in (
            (None, str(RUNNER), str(ROOT / "third_party/gem5/configs")),
            ("/runtime/gem5", "/run.py", "/runtime/gem5/configs"),
        ):
            with self.subTest(source=source), patch.dict(
                "sys.modules", modules
            ), patch.dict(os.environ):
                if source is None:
                    os.environ.pop("GEM5_SOURCE", None)
                else:
                    os.environ["GEM5_SOURCE"] = source
                with self.assertRaises(ConfigurationPath) as raised:
                    exec(
                        compile(RUNNER.read_text(), str(RUNNER), "exec"),
                        {"__file__": script_path, "__name__": "__m5_main__"},
                    )
                self.assertEqual(raised.exception.args, (expected,))


@unittest.skipUnless(shutil.which("just"), "requires just")
class LegacyRecipeDefaultsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)
        for name in (
            "justfile",
            "scripts/host/cosim_launch.sh",
            "scripts/host/cosim_lib.sh",
            "resources/devices/gpu/mi300x/gem5.yaml",
        ):
            target = self.workspace / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        shutil.copytree(
            ROOT / "resources/device_simulators",
            self.workspace / "resources/device_simulators",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        self.profile = (
            self.workspace / "resources/devices/gpu/mi300x/gem5.yaml"
        )
        self.recipe = yaml.safe_load(self.profile.read_text())

    def help(self):
        return subprocess.run(
            ["just", "--justfile", str(self.workspace / "justfile"),
             "run-launch", "--help"],
            cwd=self.workspace,
            env=dict(os.environ, COSIM_RUN_ID="recipe-defaults-test",
                     COSIM_HOST_ARCH="x86_64",
                     GEM5_BUILD_DIR="build/gem5/x86_64/VEGA_X86"),
            capture_output=True, text=True, timeout=20,
        )

    def test_help_tracks_device_recipe_defaults(self):
        for cus, size in ((7, "4GiB"), (13, "8GiB")):
            with self.subTest(cus=cus, size=size):
                recipe = self.recipe["recipe"]
                recipe["parameters"]["num_compute_units"]["default"] = cus
                recipe["defaults"]["memory_regions"][0]["size"] = size
                self.profile.write_text(yaml.safe_dump(self.recipe))
                result = self.help()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertRegex(
                    result.stdout, rf"--num-cus N[^\n]*default: {cus}\)"
                )
                self.assertRegex(
                    result.stdout, rf"--vram-size SIZE[^\n]*default: {size}\)"
                )

    def test_missing_recipe_defaults_fail_without_a_fallback(self):
        del self.recipe["recipe"]["parameters"]["num_compute_units"]
        self.profile.write_text(yaml.safe_dump(self.recipe))
        result = self.help()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("num_compute_units", result.stderr)


class Gem5RunnerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.profile = self.root / "gem5.yaml"
        self.model = self.root / "model.py"
        self.model.write_text(
            "import m5\n"
            "def add_arguments(parser, recipe):\n"
            "    parser.add_argument('--width', type=int)\n"
            "    parser.set_defaults(width=recipe['parameters']['width']['default'])\n"
            "def build(args):\n"
            "    m5.events.append(('build', args.width))\n"
            "    return object()\n"
        )
        self.m5 = ModuleType("m5")
        self.m5.events = []
        self.m5.MaxTick = 100
        self.m5.curTick = lambda: 10
        self.m5.instantiate = lambda: self.m5.events.append("instantiate")
        causes = iter(("GPU Kernel Completed", "QEMU disconnected"))

        def simulate(*args):
            self.m5.events.append(("simulate", args))
            event = ModuleType("event")
            cause = next(causes)
            event.getCause = lambda: cause
            return event

        self.m5.simulate = simulate
        utility = ModuleType("m5.util")
        utility.addToPath = lambda path: None
        self.enterContext(patch.dict("sys.modules", {
            "m5": self.m5, "m5.util": utility,
        }))

    def write_profile(self, model="model.py"):
        self.profile.write_text(yaml.safe_dump({
            "version": 1,
            "recipe": {
                "model": model,
                "parameters": {"width": {"type": "integer", "default": 2}},
            },
        }))

    def test_runner_orders_initialization_and_resumes_events(self):
        self.write_profile()
        with patch("sys.argv", [
            str(RUNNER), "--model-config", str(self.profile), "--width", "4",
        ]), redirect_stdout(io.StringIO()):
            runpy.run_path(str(RUNNER), run_name="__m5_main__")
        self.assertEqual(self.m5.events, [
            ("build", 4), "instantiate", ("simulate", ()),
            ("simulate", (90,)),
        ])

    def test_runner_uses_device_recipe_defaults(self):
        self.write_profile()
        with patch("sys.argv", [
            str(RUNNER), "--model-config", str(self.profile),
        ]), redirect_stdout(io.StringIO()):
            runpy.run_path(str(RUNNER), run_name="__m5_main__")
        self.assertEqual(self.m5.events[0], ("build", 2))

    def test_model_imports_native_and_gpufs_configuration_libraries(self):
        source = self.root / "gem5 source"
        configs = source / "configs"
        gpufs = configs / "example/gpufs"
        (gpufs / "system").mkdir(parents=True)
        (configs / "common.py").write_text("Options = object()\n")
        (gpufs / "amd.py").write_text("AmdGPUOptions = object()\n")
        (gpufs / "system/__init__.py").touch()
        (gpufs / "system/amdgpu.py").write_text("createGPU = object()\n")
        self.model.write_text(
            "from common import Options\n"
            "from amd import AmdGPUOptions\n"
            "from system.amdgpu import createGPU\n" + self.model.read_text()
        )
        self.write_profile()
        utility = sys.modules["m5.util"]
        utility.addToPath = lambda path: sys.path.insert(1, path)
        with patch.object(sys, "path", list(sys.path)), patch.dict(
            os.environ, GEM5_SOURCE=str(source)
        ), patch("sys.argv", [
            str(RUNNER), "--model-config", str(self.profile),
        ]), redirect_stdout(io.StringIO()):
            runpy.run_path(str(RUNNER), run_name="__m5_main__")
        self.assertEqual(self.m5.events[0], ("build", 2))

    def test_model_must_stay_inside_its_device_directory(self):
        outside = self.root.parent / (self.root.name + "-outside.py")
        outside.write_text("raise AssertionError('escaped model executed')\n")
        self.addCleanup(outside.unlink)
        link = self.root / "escape.py"
        link.symlink_to(outside)
        for model in ("../" + outside.name, str(outside), "escape.py"):
            self.write_profile(model)
            with self.subTest(model=model), patch("sys.argv", [
                str(RUNNER), "--model-config", str(self.profile),
            ]), self.assertRaises(ValueError):
                runpy.run_path(str(RUNNER), run_name="__m5_main__")
        self.assertEqual(self.m5.events, [])


if __name__ == "__main__":
    unittest.main()

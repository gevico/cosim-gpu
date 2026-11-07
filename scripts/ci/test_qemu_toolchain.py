# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from resources.images import toolchain


class QemuToolchainTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)
        self.installed = self.workspace / "installed"
        self.installed.mkdir()
        self.built = self.workspace / "build/qemu"
        self.built.mkdir(parents=True)
        for name in ("qemu-system-x86_64", "qemu-img"):
            path = self.installed / name
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        self.enterContext(patch.dict(os.environ, {
            "PATH": str(self.installed),
            "COSIM_IMAGE_QEMU_BIN": "",
            "COSIM_IMAGE_QEMU_IMG": "",
            "QEMU_BIN": "",
            "QEMU_IMG": "",
        }))

    def test_installed_tools_are_not_implicit_fallbacks(self):
        self.assertIsNone(toolchain.qemu_binary(self.workspace, "x86_64"))
        self.assertIsNone(toolchain.qemu_img_binary(self.workspace))

    def test_default_tools_come_from_the_same_source_build(self):
        for name in ("qemu-system-x86_64", "qemu-img"):
            path = self.built / name
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        self.assertEqual(
            toolchain.qemu_binary(self.workspace, "x86_64"),
            self.built / "qemu-system-x86_64",
        )
        self.assertEqual(
            toolchain.qemu_img_binary(self.workspace), self.built / "qemu-img"
        )

    def test_invalid_explicit_overrides_do_not_select_another_tool(self):
        for name in ("qemu-system-x86_64", "qemu-img"):
            path = self.built / name
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        for variable, resolve in (
            (
                "COSIM_IMAGE_QEMU_BIN",
                lambda: toolchain.qemu_binary(self.workspace, "x86_64"),
            ),
            (
                "QEMU_BIN",
                lambda: toolchain.qemu_binary(self.workspace, "x86_64"),
            ),
            (
                "COSIM_IMAGE_QEMU_IMG",
                lambda: toolchain.qemu_img_binary(self.workspace),
            ),
            ("QEMU_IMG", lambda: toolchain.qemu_img_binary(self.workspace)),
        ):
            with self.subTest(variable=variable), patch.dict(
                os.environ, {variable: "missing-tool"}
            ):
                self.assertIsNone(resolve())

    def test_explicit_overrides_are_still_honored(self):
        with patch.dict(os.environ, {
            "QEMU_BIN": "qemu-system-x86_64",
            "QEMU_IMG": str(self.installed / "qemu-img"),
        }):
            self.assertEqual(
                toolchain.qemu_binary(self.workspace, "x86_64"),
                self.installed / "qemu-system-x86_64",
            )
            self.assertEqual(
                toolchain.qemu_img_binary(self.workspace),
                self.installed / "qemu-img",
            )

    def test_packer_executes_the_selected_image_helper(self):
        for name in ("qemu-img", "custom-image-helper"):
            with self.subTest(name=name):
                helper = self.built / name
                helper.write_text("#!/bin/sh\necho selected-helper\n")
                helper.chmod(0o755)
                environment = toolchain.packer_environment(
                    self.workspace, helper, self.workspace / "stage" / name
                )
                output = subprocess.check_output(
                    ["qemu-img", "--version"], text=True, env=environment
                )
                self.assertEqual(output.strip(), "selected-helper")


@unittest.skipUnless(shutil.which("just"), "requires just")
class QemuBuildTargetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)
        source = Path(__file__).resolve().parents[2]
        for name in (
            "justfile", "scripts/host/build.sh", "scripts/host/dev.sh",
        ):
            target = self.workspace / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, target)
        shutil.copytree(source / "resources",
                        self.workspace / "resources",
                        ignore=shutil.ignore_patterns("__pycache__"))
        # Only the disposable-runner cleanup and external build tools are fakes.
        prepare = self.workspace / "scripts/ci/prepare_image_host.sh"
        prepare.parent.mkdir(parents=True)
        prepare.write_text(
            '#!/bin/sh\ntest "$#" -eq 1 || exit 2\n'
            'printf "%s" "$1" > prepare-recipe.txt\n'
        )
        tools = self.workspace / "tools"
        tools.mkdir()
        for name in ("make", "sudo", "git"):
            path = tools / name
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        self.environment = dict(
            os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"],
            COSIM_ENV="host", COSIM_HOST_ARCH="x86_64", JOBS="1",
        )
        configure = self.workspace / "third_party/qemu/configure"
        configure.parent.mkdir(parents=True)
        configure.write_text(
            "#!" + sys.executable + "\n"
            "import json, os, pathlib, sys\n"
            "root = pathlib.Path.cwd()\n"
            "with (root / 'configure.jsonl').open('a') as log:\n"
            "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "targets = next(x.split('=', 1)[1] for x in sys.argv[1:] "
            "if x.startswith('--target-list=')).split(',')\n"
            "(root / 'config-host.mak').write_text("
            "'TARGET_DIRS=' + ' '.join(targets) + '\\n')\n"
            "(root / 'build.ninja').touch()\n"
            "server = os.environ.get('FIXTURE_VFIO_SERVER', 'y')\n"
            "for target in targets:\n"
            "    (root / (target + '-config-devices.mak')).write_text(\n"
            "        'CONFIG_VFIO_USER_SERVER=' + server + '\\n')\n"
            "names = ['qemu-system-' + t.removesuffix('-softmmu') "
            "for t in targets] + ['qemu-img', 'qemu-io']\n"
            "for name in names:\n"
            "    tool = root / name\n"
            "    tool.write_text('#!/bin/sh\\nif [ \"$1\" = -object ]; then\\n'\n"
            "        + ('echo x-vfio-user-server' if server == 'y' "
            "else 'true')\n"
            "        + '\\nelse\\necho vfio-user-pci fixture-version\\nfi\\n')\n"
            "    tool.chmod(0o755)\n"
        )
        configure.chmod(0o755)

    def run_recipe(self, *arguments):
        return subprocess.run(
            ["just", *arguments], cwd=self.workspace, env=self.environment,
            capture_output=True, text=True, timeout=20,
        )

    def configurations(self):
        path = self.workspace / "build/qemu/configure.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def test_requested_guests_reconfigure_without_stale_binary_reuse(self):
        for architecture in ("riscv64", "aarch64", "riscv64"):
            with self.subTest(architecture=architecture):
                result = self.run_recipe("build-qemu", "1", architecture)
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = "--target-list=x86_64-softmmu," + architecture
                expected += "-softmmu"
                self.assertIn(expected, self.configurations()[-1])
                self.assertIsNotNone(toolchain.qemu_binary(
                    self.workspace, architecture
                ))
                self.assertIsNotNone(toolchain.qemu_binary(
                    self.workspace, "x86_64"
                ))
        self.assertEqual(len(self.configurations()), 3)
        result = self.run_recipe("build-qemu", "1", "riscv64")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.configurations()), 3)

    def test_default_build_remains_native_and_invalid_target_fails(self):
        result = self.run_recipe("build-qemu", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--target-list=x86_64-softmmu", self.configurations()[0])
        result = self.run_recipe("build-qemu", "1", "invalid")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported QEMU target", result.stderr)
        self.assertEqual(len(self.configurations()), 1)

    def test_image_preparation_uses_the_recipe_guest_architecture(self):
        identifier = "openruyi/2026.09/riscv64/rocm/7.2.4"
        result = self.run_recipe("ci-prepare-image-host", identifier)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--target-list=x86_64-softmmu,riscv64-softmmu",
                      self.configurations()[0])
        self.assertIsNotNone(toolchain.qemu_binary(self.workspace, "riscv64"))
        self.assertIsNotNone(toolchain.qemu_img_binary(self.workspace))
        self.assertEqual(
            (self.workspace / "prepare-recipe.txt").read_text(), identifier
        )

    def test_target_without_vfio_server_reuses_its_valid_configuration(self):
        self.environment["FIXTURE_VFIO_SERVER"] = "n"
        for _ in range(2):
            result = self.run_recipe("build-qemu", "1")
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.configurations()), 1)


if __name__ == "__main__":
    unittest.main()

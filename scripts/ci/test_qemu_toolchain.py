# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
import os
import subprocess
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


if __name__ == "__main__":
    unittest.main()

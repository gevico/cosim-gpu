# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

import yaml

from run_rocm import Inputs, load_regression, topology
from runtime_artifact import ROOT


RECIPES = (
    "ubuntu/24.04/x86_64/rocm/7.0",
    "openruyi/2026.09/riscv64/rocm/7.2.4",
)


class RegressionProfileTests(unittest.TestCase):
    def test_production_entry_point_works_without_pythonpath(self):
        result = subprocess.run([
            "just", "test-rocm-regression", "unused-output", "unused-assets",
            RECIPES[0], "--help",
        ], cwd=ROOT, env={**os.environ, "COSIM_ENV": "host", "PYTHONPATH": ""},
            capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--recipe", result.stdout)

    def test_each_profile_uses_its_machine_and_guest_preparation(self):
        for identifier in RECIPES:
            with self.subTest(recipe=identifier):
                recipe, machine, prepare = load_regression(identifier)
                self.assertEqual(recipe.identifier, identifier)
                self.assertTrue(machine.is_file())
                self.assertTrue(prepare.is_relative_to(recipe.directory))
                self.assertTrue(prepare.is_file())
                subprocess.run(["bash", "-n", str(prepare)], check=True)

    def test_topology_preserves_recipe_boot_configuration(self):
        with tempfile.TemporaryDirectory() as name:
            share = Path(name)
            for identifier in RECIPES:
                with self.subTest(recipe=identifier):
                    recipe, _, _ = load_regression(identifier)
                    inputs = Inputs(
                        output=share, assets=recipe.output_path(ROOT),
                        launcher=share / "cosim", gem5=share / "gem5.opt",
                        qemu=ROOT / "build/qemu" / (
                            "qemu-system-" + recipe.architecture
                        ), recipe=identifier, boot_timeout=600,
                        test_timeout=300,
                    )
                    document = topology(inputs, share)
                    machine = document["machines"][0]
                    self.assertEqual(machine["vhost"]["image"], identifier)
                    self.assertEqual(
                        machine["vhost"]["runtime"]["binary"], str(inputs.qemu)
                    )
                    self.assertEqual(machine["vhost"]["memory"], "4G")
                    self.assertEqual(machine["vhost"]["cpus"], 2)
                    self.assertEqual(
                        machine["devices"][0]["runtime"]["binary"],
                        str(inputs.gem5),
                    )
                    self.assertTrue(all(Path(p).is_absolute()
                                        for p in document["imports"]))
                    if recipe.architecture == "riscv64":
                        self.assertEqual(machine["vhost"]["use"], "vhost-riscv")
                        self.assertIn(
                            "root=/dev/vda2", machine["vhost"]["cmdline"]
                        )
                    else:
                        self.assertIn("node1", document["templates"])

    def test_common_guest_runner_compiles_every_program(self):
        runner = ROOT / "tests/rocm_regression.sh"
        subprocess.run(["bash", "-n", str(runner)], check=True)
        source = runner.read_text()
        self.assertNotIn("/opt/rocm", source)
        self.assertNotIn("cosim-gpu-initialize.service", source)
        self.assertIn('source "$share/prepare.sh"', source)
        self.assertIn('"BUILDDIR=build" "build/$program"', source)


class OpenRuyiBootMountTests(unittest.TestCase):
    def optional_efi(self, fstab):
        recipe = ROOT / "resources/images/recipes" / RECIPES[1]
        tasks = yaml.safe_load((recipe / "provision.yml").read_text())[0]["tasks"]
        policies = [task["ansible.builtin.replace"] for task in tasks
                    if task.get("ansible.builtin.replace", {}).get("path")
                    == "/etc/fstab"]
        self.assertEqual(len(policies), 1)
        policy = policies[0]
        return re.sub(policy["regexp"], policy["replace"], fstab,
                      flags=re.MULTILINE)

    def test_only_efi_becomes_optional_and_provisioning_is_idempotent(self):
        other = ("# UUID=comment /boot/efi vfat defaults 0 2\n"
                 "UUID=root / xfs defaults 0 1\n"
                 "UUID=home /home xfs defaults 0 2\n"
                 "UUID=other /boot/efi-backup vfat defaults 0 2\n")
        for options in ("defaults", "umask=0077,x-systemd.device-timeout=45",
                        "defaults,nofail,noatime"):
            with self.subTest(options=options):
                entry = f"  UUID=E427-9719\t/boot/efi\tvfat\t{options} 0 2\n"
                result = self.optional_efi(other + entry)
                self.assertTrue(result.startswith(other))
                fields = result.splitlines()[-1].split()
                self.assertEqual(fields[:3], [
                    "UUID=E427-9719", "/boot/efi", "vfat",
                ])
                expected = options.split(",")
                if "nofail" not in expected:
                    expected.append("nofail")
                self.assertEqual(fields[3].split(","), expected)
                self.assertEqual(fields[4:], ["0", "2"])
                self.assertEqual(self.optional_efi(result), result)

    def test_systemd_does_not_require_the_optional_efi_mount(self):
        original = "UUID=E427-9719 /boot/efi vfat defaults 0 2\n"
        optional = self.optional_efi(original)
        generator = "/usr/lib/systemd/system-generators/systemd-fstab-generator"
        for fstab, required in ((original, True), (optional, False)):
            with self.subTest(required=required), \
                    tempfile.TemporaryDirectory() as name:
                root = Path(name)
                table = root / "fstab"
                table.write_text(fstab)
                outputs = [root / part for part in ("normal", "early", "late")]
                for output in outputs:
                    output.mkdir()
                result = subprocess.run([
                    generator, *map(str, outputs),
                ], env={**os.environ, "SYSTEMD_FSTAB": str(table),
                        "SYSTEMD_SYSROOT_FSTAB": "/dev/null"},
                    capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue((outputs[0] / "boot-efi.mount").is_file())
                for relation, expected in (("requires", required),
                                           ("wants", not required)):
                    link = (outputs[0] / f"local-fs.target.{relation}"
                            / "boot-efi.mount")
                    self.assertEqual(link.is_symlink(), expected)


if __name__ == "__main__":
    unittest.main()

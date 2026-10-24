# SPDX-License-Identifier: Apache-2.0

import subprocess
import unittest

import yaml

from run_rocm import PROGRAMS, VHOST_REGRESSION_SCRIPT
from runtime_artifact import ROOT
from resources.images.recipe import load_recipe


def recipe_tasks(recipe):
    playbook = yaml.safe_load(recipe.playbook_file.read_text(encoding="utf-8"))
    return playbook[0]["tasks"]


class GuestBuildTargetTests(unittest.TestCase):
    def test_guest_build_directory_matches_the_makefile_targets(self):
        script = (
            ROOT / "resources/images/recipes/ubuntu/24.04/x86_64/"
            "rocm/7.0/files/cosim_rocm_regression.sh"
        ).read_text()
        self.assertIn('make -j1 "BUILDDIR=build" "build/$program"', script)
        for program in PROGRAMS:
            with self.subTest(program=program):
                result = subprocess.run(
                    [
                        "make", "--question", "-C", str(ROOT / "tests"),
                        "BUILDDIR=build", f"build/{program}",
                    ],
                    capture_output=True, text=True, check=False,
                )
                self.assertIn(
                    result.returncode,
                    (0, 1),
                    f"make could not resolve build/{program}: {result.stderr}",
                )

    def test_vhost_scripts_are_recipe_files(self):
        recipe = load_recipe(
            ROOT, "ubuntu/24.04/x86_64/rocm/7.0"
        )
        tasks = recipe_tasks(recipe)
        install_task = next(
            task for task in tasks if task["name"] == "Install recipe files"
        )
        destinations = {
            item["source"]: item["destination"]
            for item in install_task["loop"]
        }
        expected = {
            "cosim_gpu_initialize.sh": "/usr/local/bin/cosim-gpu-initialize.sh",
            "cosim_rocm_regression.sh": VHOST_REGRESSION_SCRIPT,
        }
        for filename, destination in expected.items():
            with self.subTest(filename=filename):
                script = recipe.directory / "files" / filename
                self.assertTrue(script.is_file())
                self.assertEqual(script.parent, recipe.directory / "files")
                source = f"{{{{ playbook_dir }}}}/files/{filename}"
                self.assertEqual(destinations[source], destination)

    def test_serial_console_override_is_installed_for_ttyS0(self):
        recipe = load_recipe(
            ROOT, "ubuntu/24.04/x86_64/rocm/7.0"
        )
        tasks = recipe_tasks(recipe)
        install_task = next(
            task for task in tasks if task["name"] == "Install recipe files"
        )
        override_input = (
            "{{ playbook_dir }}/files/serial-getty-override.conf"
        )
        override = next(
            item for item in install_task["loop"]
            if item["source"] == override_input
        )

        self.assertEqual(
            override["destination"],
            "/etc/systemd/system/serial-getty@ttyS0.service.d/override.conf",
        )
        content = (
            recipe.directory / "files/serial-getty-override.conf"
        ).read_text()
        self.assertIn("ExecStart=\n", content)
        self.assertIn("--autologin root", content)

    def test_amdgpu_dkms_is_pinned_to_the_verified_package(self):
        recipe = load_recipe(
            ROOT, "ubuntu/24.04/x86_64/rocm/7.0"
        )
        tasks = recipe_tasks(recipe)
        dkms_task = next(
            task for task in tasks
            if task["name"] == "Install and build the AMDGPU DKMS module"
        )
        package_task = next(
            task for task in dkms_task["block"]
            if task["name"] == "Install the AMDGPU DKMS package"
        )

        self.assertEqual(
            recipe.variables["amdgpu_dkms_version"],
            "1:6.14.14.30100000-2204008.24.04",
        )
        self.assertIn(
            "amdgpu-dkms={{ cosim_recipe_variables.amdgpu_dkms_version }}",
            package_task["ansible.builtin.apt"]["name"],
        )

        rocm_task = next(
            task for task in tasks
            if task["name"] == "Install the ROCm stack"
        )
        self.assertEqual(rocm_task["ansible.builtin.apt"]["name"], "rocm")

    def test_dkms_failure_path_prints_logs_and_fails_the_build(self):
        recipe = load_recipe(
            ROOT, "ubuntu/24.04/x86_64/rocm/7.0"
        )
        tasks = recipe_tasks(recipe)
        dkms_task = next(
            task for task in tasks
            if task["name"] == "Install and build the AMDGPU DKMS module"
        )

        package_task = next(
            task for task in dkms_task["block"]
            if task["name"] == "Install the AMDGPU DKMS package"
        )
        autoinstall_task = next(
            task for task in dkms_task["block"]
            if task["name"] == "Run DKMS autoinstall for the selected kernel"
        )
        self.assertLess(
            dkms_task["block"].index(package_task),
            dkms_task["block"].index(autoinstall_task),
        )
        rescue_tasks = dkms_task["rescue"]
        discovery_task = next(
            task for task in rescue_tasks
            if task["name"] == "Find AMDGPU DKMS build logs"
        )
        log_task = next(
            task for task in rescue_tasks
            if task["name"] == "Read AMDGPU DKMS build logs"
        )
        display_task = next(
            task for task in rescue_tasks
            if task["name"] == "Display AMDGPU DKMS build logs"
        )
        failure_task = rescue_tasks[-1]

        self.assertLess(
            rescue_tasks.index(discovery_task), rescue_tasks.index(log_task)
        )
        self.assertLess(
            rescue_tasks.index(log_task), rescue_tasks.index(display_task)
        )
        self.assertLess(
            rescue_tasks.index(display_task), rescue_tasks.index(failure_task)
        )
        self.assertEqual(
            discovery_task["ansible.builtin.find"],
            {
                "paths": "/var/lib/dkms/amdgpu",
                "patterns": "make.log",
                "recurse": True,
            },
        )
        self.assertEqual(discovery_task["register"], "amdgpu_dkms_logs")

        self.assertEqual(
            log_task["ansible.builtin.command"]["argv"],
            ["cat", "{{ item.path }}"],
        )
        self.assertEqual(
            log_task["loop"], "{{ amdgpu_dkms_logs.files | default([]) }}"
        )
        self.assertEqual(log_task["register"], "amdgpu_dkms_log_output")
        self.assertIs(log_task["changed_when"], True)
        self.assertEqual(
            display_task["ansible.builtin.debug"]["msg"], "{{ item.stdout }}"
        )
        self.assertEqual(
            display_task["loop"],
            "{{ amdgpu_dkms_log_output.results | default([]) }}",
        )
        self.assertEqual(
            failure_task["name"], "Report AMDGPU DKMS build failure"
        )
        self.assertIn("ansible.builtin.fail", failure_task)

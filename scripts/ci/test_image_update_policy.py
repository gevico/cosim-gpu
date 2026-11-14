# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]


class ImageUpdatePolicyTests(unittest.TestCase):
    def test_automatic_updates_are_disabled_before_package_operations(self):
        recipe = ROOT / "resources/images/recipes/ubuntu/24.04/x86_64/rocm/7.0"
        playbook = yaml.safe_load((recipe / "provision.yml").read_text())
        tasks = playbook[0]["tasks"]
        package = next(i for i, task in enumerate(tasks)
                       if "ansible.builtin.apt" in task)
        policy = next((i, task) for i, task in enumerate(tasks)
                      if "APT::Periodic::Enable" in
                      task.get("ansible.builtin.copy", {}).get("content", ""))
        self.assertLess(policy[0], package)
        self.assertIn('APT::Periodic::Enable "0";',
                      policy[1]["ansible.builtin.copy"]["content"])
        with tempfile.TemporaryDirectory() as name:
            config = Path(name) / "apt-policy.conf"
            config.write_text(policy[1]["ansible.builtin.copy"]["content"])
            result = subprocess.check_output([
                "apt-config", "-c", str(config), "shell", "enabled",
                "APT::Periodic::Enable",
            ], text=True)
        self.assertEqual(result.strip(), "enabled='0'")
        systemd = [(i, task) for i, task in enumerate(tasks)
                   if "ansible.builtin.systemd_service" in task]
        timers = next((i, task) for i, task in systemd
                      if "apt-daily.timer" in task.get("loop", []))
        services = next((i, task) for i, task in systemd
                        if "apt-daily.service" in task.get("loop", []))
        self.assertLess(timers[0], services[0])
        self.assertLess(services[0], package)
        self.assertEqual(set(timers[1]["loop"]), {
            "apt-daily.timer", "apt-daily-upgrade.timer",
        })
        self.assertEqual(set(services[1]["loop"]), {
            "apt-daily.service", "apt-daily-upgrade.service",
        })
        timer = timers[1]["ansible.builtin.systemd_service"]
        self.assertTrue(timer["masked"])
        self.assertFalse(timer["enabled"])
        self.assertEqual(timer["state"], "stopped")
        service = services[1]
        self.assertTrue(service["ansible.builtin.systemd_service"]["masked"])
        self.assertNotIn("state", service["ansible.builtin.systemd_service"])
        self.assertIn(service["register"] + ".status.ActiveState",
                      service["until"])
        self.assertIn("inactive", service["until"])
        self.assertGreater(service["retries"], 1)
        self.assertGreater(service["delay"], 0)
        self.assertLessEqual(service["retries"] * service["delay"], 900)
        self.assertNotIn("ignore_errors", service)
        self.assertNotIn("failed_when", service)


if __name__ == "__main__":
    unittest.main()

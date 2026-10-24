# SPDX-License-Identifier: Apache-2.0

import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import tempfile
import time
import unittest
import uuid

import yaml

from ci_lifecycle import Lifecycle
from run_rocm import Inputs, archive, stop, topology
from runtime_artifact import ROOT


class LauncherLifecycleTests(unittest.TestCase):
    def test_rocm_plan_respects_runner_budget_and_external_parameters(self):
        launcher = Path(os.environ.get(
            "CARGO_TARGET_DIR", ROOT / "build/cargo/host"
        ))
        launcher = launcher / "release/cosim"
        session_parent = ROOT / ".cosim"
        session_parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            dir=session_parent, prefix="ci-plan-"
        ) as name:
            directory = Path(name)
            for options, budget in (({}, 8 << 30), (
                {"memory": "3G", "vram": "2G", "cpus": 1}, 5 << 30
            )):
                with self.subTest(options=options):
                    inputs = Inputs(
                        output=directory, assets=directory, launcher=launcher,
                        gem5=ROOT / "build/gem5/x86_64/VEGA_X86/gem5.opt",
                        qemu=ROOT / "build/qemu/qemu-system-x86_64",
                        boot_timeout=300, test_timeout=300, **options,
                    )
                    generated = topology(inputs, directory)
                    generated_machine = generated["machines"][0]
                    self.assertEqual(
                        generated_machine["vhost"]["memory"], inputs.memory
                    )
                    self.assertEqual(
                        generated_machine["vhost"]["cpus"], inputs.cpus
                    )
                    device = generated_machine["devices"][0]
                    region = device["memory_regions"][0]
                    self.assertEqual(region["size"], inputs.vram)
                    config = directory / "topology.yaml"
                    config.write_text(yaml.safe_dump({
                        "version": 1,
                        "imports": [
                            str(ROOT / "resources/vhosts/qemu.yaml"),
                            str(ROOT / "resources/vhosts/vhost-x86-tcg.yaml"),
                        ],
                        "machines": [{
                            "id": "m0",
                            "vhost": {
                                "use": "vhost-x86-tcg",
                                "image": "ubuntu/24.04/x86_64/rocm/7.0",
                                "cmdline": (
                                    "console=ttyS0 root=/dev/vda1 rw nokaslr "
                                    "modprobe.blacklist=amdgpu"
                                ),
                                "runtime": {"binary": str(inputs.qemu)},
                                "memory": inputs.memory,
                                "cpus": inputs.cpus,
                            },
                        }],
                    }))
                    plan = json.loads(subprocess.check_output([
                        str(launcher), "run", str(config),
                        "--dry-run",
                        "--run-dir", str(directory / "run"),
                    ]))
                    self.assertLessEqual(
                        plan["launch"]["machines"][0]["memory"]["size"],
                        budget,
                    )
                    self.assertEqual(
                        plan["images"][0]["recipe"]["id"],
                        "ubuntu/24.04/x86_64/rocm/7.0",
                    )
                    vhost = next(p for p in plan["launch"]["processes"]
                                 if p["role"] == "vhost")
                    argv = vhost["argv"]
                    self.assertEqual(
                        argv[argv.index("-smp") + 1], str(inputs.cpus)
                    )

    def exercise(self, close_input: bool) -> None:
        launcher = Path(os.environ.get(
            "CARGO_TARGET_DIR", ROOT / "build/cargo/host"
        ))
        launcher = launcher / "release/cosim"
        if platform.machine() == "aarch64":
            vhost_template = "vhost-arm-tcg"
        else:
            vhost_template = "vhost-x86-tcg"
        output = ROOT / "artifacts/ci-check" / uuid.uuid4().hex[:8]
        output.mkdir(parents=True)
        session_parent = ROOT / ".cosim"
        session_parent.mkdir(exist_ok=True)
        reader, writer = os.pipe()
        try:
            with tempfile.TemporaryDirectory(
                dir=session_parent, prefix="ci-test-"
            ) as name:
                directory = Path(name)
                session = directory / "run"
                pool = directory / "pool"
                pid_file = directory / "qemu.pid"
                config = directory / "topology.yaml"
                config.write_text(yaml.safe_dump({
                    "version": 1,
                    "imports": [
                        str(ROOT / "resources/vhosts" / path)
                        for path in ("qemu.yaml", f"{vhost_template}.yaml")
                    ],
                    "machines": [{"id": "m0", "vhost": {
                        "use": vhost_template,
                        "args": [
                            "-S", "-nodefaults", "-pidfile", str(pid_file)
                        ],
                    }}],
                }))
                log_path = output / "launcher.log"
                with Lifecycle(reader).installed() as lifecycle:
                    with log_path.open("wb") as log:
                        process = subprocess.Popen([
                            str(launcher), "run", str(config), "--run-dir",
                            str(session), "--pool-dir", str(pool),
                            "--stdin-lifeline", "--ready-timeout", "15",
                        ], stdin=subprocess.PIPE, stdout=log,
                            stderr=subprocess.STDOUT)
                        with lifecycle.own(process):
                            try:
                                deadline = time.monotonic() + 20
                                while (
                                    b"ready: m0.vhost"
                                    not in log_path.read_bytes()
                                ):
                                    if process.poll() is not None:
                                        self.fail(log_path.read_text())
                                    if time.monotonic() >= deadline:
                                        self.fail("QEMU readiness timed out")
                                    time.sleep(0.05)
                                pid = int(pid_file.read_text())
                                if close_input:
                                    os.close(writer)
                                    writer = -1
                                else:
                                    os.kill(os.getpid(), signal.SIGTERM)
                                self.assertEqual(process.wait(timeout=20), 0)
                            finally:
                                try:
                                    stop(process, session)
                                finally:
                                    archive(session, output)
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)
                self.assertFalse(pool.exists())
                verdict = json.loads(
                    (output / "session/verdict.json").read_text()
                )
                self.assertEqual(verdict["status"], "PASS")
                self.assertTrue(verdict["users_stopped"])
                self.assertEqual(verdict["cleanup_errors"], [])
                vhost_log = output / "session/m0/vhost/output.log"
                self.assertTrue(vhost_log.exists())
        finally:
            os.close(reader)
            if writer >= 0:
                os.close(writer)

    def test_terminated_runner_cleans_qemu_and_keeps_evidence(self) -> None:
        self.exercise(close_input=False)

    def test_closed_input_cleans_qemu_and_keeps_evidence(self) -> None:
        self.exercise(close_input=True)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import socket
import subprocess
import sys
import time
import tomllib
import uuid

import pexpect
from pexpect.fdpexpect import fdspawn
import yaml

from scripts.ci.guest_console import GuestConsole
from scripts.ci.ci_lifecycle import Lifecycle
from scripts.ci.runtime_artifact import ROOT, sha256
from resources.images.bundle import verify_bundle
from resources.images.recipe import load_recipe
from resources.images.toolchain import qemu_binary


PROGRAMS = (
    "vector_add", "gemm", "reduction", "transpose", "prefix_scan", "histogram"
)
VHOST_REGRESSION_SCRIPT = "/mnt/cosim-ci/rocm_regression.sh"


@dataclass(frozen=True)
class Inputs:
    output: Path
    assets: Path
    launcher: Path
    gem5: Path
    qemu: Path
    recipe: str
    boot_timeout: int
    test_timeout: int
    memory: str = "4G"
    vram: str = "4G"
    cpus: int = 2


@dataclass
class Result:
    program: str
    status: str = "FAIL"
    reason: str = "execution incomplete"
    elapsed_seconds: float = 0


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def load_regression(identifier: str):
    recipe = load_recipe(ROOT, identifier)
    profile = tomllib.loads(
        (recipe.directory / "regression.toml").read_text(encoding="utf-8")
    )
    if set(profile) != {"machine", "prepare"}:
        raise ValueError("regression profile requires machine and prepare")
    machine = (ROOT / profile["machine"]).resolve()
    prepare = (recipe.directory / profile["prepare"]).resolve()
    if not machine.is_relative_to(ROOT / "resources/machines"):
        raise ValueError("regression machine must stay in resources/machines")
    if not prepare.is_relative_to(recipe.directory):
        raise ValueError("guest preparation must stay in its image recipe")
    if not machine.is_file() or not prepare.is_file():
        raise ValueError("regression machine or preparation script is missing")
    return recipe, machine, prepare


def prepare(inputs: Inputs) -> dict:
    recipe, machine, guest_prepare = load_regression(inputs.recipe)
    if platform.system() != "Linux":
        raise RuntimeError("the ROCm regression runner requires Linux")
    if recipe.accelerator == "kvm":
        if platform.machine() != recipe.architecture:
            raise RuntimeError(
                "KVM requires matching Host and vHost architectures"
            )
        with Path("/dev/kvm").open("rb+"):
            pass
    metadata = verify_bundle(ROOT, recipe, inputs.assets)
    for path in (inputs.launcher, inputs.gem5, inputs.qemu):
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError(f"missing executable: {path}")
    provenance = {"assets": metadata, "binaries": {}, "sources": {}}
    provenance["regression"] = {
        "recipe": inputs.recipe,
        "files": {str(path): sha256(path) for path in (
            recipe.directory / "regression.toml", machine, guest_prepare,
            ROOT / "tests/rocm_regression.sh",
        )},
    }
    for path in (inputs.launcher, inputs.gem5, inputs.qemu):
        provenance["binaries"][str(path)] = sha256(path)
    rom = (
        ROOT
        / "third_party/gem5-resources/src/x86-ubuntu-gpu-ml/files/mi300.rom"
    )
    provenance["firmware"] = {str(rom): sha256(rom)}
    patch_dir = inputs.output / "patch"
    patch_dir.mkdir()
    repositories = (
        ("project", ROOT),
        ("gem5", ROOT / "third_party/gem5"),
        ("qemu", ROOT / "third_party/qemu"),
        ("gem5-resources", ROOT / "third_party/gem5-resources"),
    )
    for name, directory in repositories:
        revision = subprocess.check_output(
            ["git", "-C", str(directory), "rev-parse", "HEAD"], text=True
        ).strip()
        patch = patch_dir / f"{name}.patch"
        with patch.open("wb") as destination:
            subprocess.run(
                ["git", "-C", str(directory), "diff", "--binary", "HEAD"],
                stdout=destination, check=True,
            )
        status = subprocess.check_output([
            "git", "-C", str(directory), "status", "--porcelain",
            "--untracked-files=no",
        ])
        (patch_dir / f"{name}-status.txt").write_bytes(status)
        untracked = subprocess.check_output([
            "git", "-C", str(directory), "ls-files", "--others",
            "--exclude-standard", "--", ".", ":(exclude)artifacts/**",
        ])
        if untracked:
            raise ValueError(f"untracked source files in {name}: {untracked!r}")
        provenance["sources"][name] = {
            "head_commit": revision,
            "source_fingerprint": hashlib.sha256(
                revision.encode() + patch.read_bytes()
            ).hexdigest(),
        }
    write_json(inputs.output / "provenance.json", provenance)
    return metadata


def topology(inputs: Inputs, share: Path) -> dict:
    _, source, _ = load_regression(inputs.recipe)
    document = yaml.safe_load(source.read_text())
    imports = []
    for name in document.get("imports", []):
        path = source.parent / name
        if not path.exists():
            path = ROOT / "resources" / name
        imports.append(str(path.resolve()))
    document["imports"] = imports
    if len(document["machines"]) != 1:
        raise ValueError("GPU regression requires one machine per session")
    machine = document["machines"][0]
    machine["id"] = "m0"
    vhost = machine.setdefault("vhost", {})
    # Console readiness belongs to the runner, not a template login marker.
    vhost.pop("serial", None)
    vhost.update({
        "image": inputs.recipe, "memory": inputs.memory, "cpus": inputs.cpus,
        "runtime": {"binary": str(inputs.qemu)},
    })
    vhost.setdefault("args", []).extend([
        "-virtfs", "local,path=" + str(share).replace(",", ",,")
        + ",mount_tag=cosimci,security_model=none,readonly=on",
    ])
    devices = machine.setdefault("devices", [{"use": "mi300x"}])
    if len(devices) != 1:
        raise ValueError("GPU regression requires one device per session")
    devices[0].update({
        "id": "gpu", "runtime": {"binary": str(inputs.gem5)},
        "memory_regions": [{
            "name": "vram", "size": inputs.vram, "align": "2M",
        }],
    })
    return document


def connect(
    path: Path, process: subprocess.Popen, timeout: int, lifecycle: Lifecycle
) -> socket.socket:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        lifecycle.check()
        if process.poll() is not None:
            raise RuntimeError(
                f"launcher exited before vHost boot: {process.returncode}"
            )
        stream = socket.socket(socket.AF_UNIX)
        try:
            stream.connect(str(path))
            return stream
        except (FileNotFoundError, ConnectionRefusedError):
            stream.close()
            time.sleep(0.2)
    raise TimeoutError("vHost serial socket did not appear")


def stop(process: subprocess.Popen, session: Path) -> None:
    assert process.stdin is not None
    process.stdin.close()
    try:
        status = process.wait(timeout=60)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        raise RuntimeError("launcher cleanup exceeded 60 seconds")
    verdict = json.loads((session / "verdict.json").read_text())
    if (status != 0 or verdict["status"] != "PASS"
            or not verdict["users_stopped"] or verdict["cleanup_errors"]):
        raise RuntimeError(f"launcher cleanup failed: {verdict}")


def archive(session: Path, output: Path) -> None:
    for path in session.rglob("*"):
        if path.is_file() and path.suffix in (".json", ".log", ".txt"):
            destination = output / "session" / path.relative_to(session)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def exercise_vhost(
    stream: socket.socket, row: Path, inputs: Inputs, program: str
) -> None:
    transport = fdspawn(stream, timeout=inputs.boot_timeout)
    with (row / "console.log").open("wb") as console_log:
        transport.logfile_read = console_log
        transport.sendline(b"")
        transport.expect(
            rb"root@[^\r\n]+[#$] ", timeout=inputs.boot_timeout
        )
        console = GuestConsole(transport)
        console.run(
            "mkdir -p /mnt/cosim-ci && mount -t 9p "
            "-o trans=virtio,version=9p2000.L,ro cosimci /mnt/cosim-ci", 30
        ).require_success()
        outcome = console.run(
            f"bash {shlex.quote(VHOST_REGRESSION_SCRIPT)} "
            f"{shlex.quote(program)} {inputs.test_timeout}",
            inputs.test_timeout + 600,
        )
        name = "gemm_tiled" if program == "gemm" else program
        outcome.require_workload(name)
        if b"[COSIM_ENV] HSA_ENABLE_INTERRUPT=0" not in outcome.output:
            raise RuntimeError("vHost environment was not confirmed")


def run_case(inputs: Inputs, program: str, lifecycle: Lifecycle) -> Result:
    started = time.monotonic()
    row = inputs.output / program
    row.mkdir()
    result = Result(program)
    session = ROOT / ".cosim" / ("ci-" + uuid.uuid4().hex[:8])
    share = row / "share"
    share.mkdir()
    for name in ("kernels", "common"):
        shutil.copytree(ROOT / "tests" / name, share / name)
    shutil.copy2(ROOT / "tests/Makefile", share / "Makefile")
    shutil.copy2(ROOT / "tests/rocm_regression.sh", share)
    shutil.copy2(load_regression(inputs.recipe)[2], share / "prepare.sh")
    source = ROOT / "tests/kernels" / f"{program}.cpp"
    config = row / "topology.yaml"
    config.write_text(yaml.safe_dump(topology(inputs, share)))
    command = [
        str(inputs.launcher), "run", str(config),
        "--run-dir", str(session),
        "--ready-timeout", str(inputs.boot_timeout), "--stdin-lifeline",
    ]
    write_json(row / "run-manifest.json", {
        "program": str(source.relative_to(ROOT)),
        "source_sha256": sha256(source), "mode": "pure_test", "repeat": 1,
        "vhost_environment": {"HSA_ENABLE_INTERRUPT": "0"},
        "boot_timeout": inputs.boot_timeout,
        "test_timeout": inputs.test_timeout,
        "artifact_dir": str(row), "command": command,
        "gem5_binary": str(inputs.gem5),
        "vhost_script": VHOST_REGRESSION_SCRIPT,
        "runner_argument": program,
        "recipe": inputs.recipe,
    })
    try:
        with (row / "launcher.log").open("wb") as log:
            process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=log,
                stderr=subprocess.STDOUT,
            )
            with lifecycle.own(process):
                try:
                    with connect(
                        session / "m0/serial.sock", process,
                        inputs.boot_timeout, lifecycle,
                    ) as stream:
                        exercise_vhost(stream, row, inputs, program)
                    lifecycle.check()
                finally:
                    stop(process, session)
        result.status = "PASS"
        result.reason = "numerical result and exit status verified"
    except (
        OSError, ValueError, RuntimeError, pexpect.ExceptionPexpect
    ) as error:
        result.reason = lifecycle.reason or str(error)
    finally:
        archive(session, row)
        result.elapsed_seconds = round(time.monotonic() - started, 3)
        write_json(row / "verdict.json", asdict(result))
    print(json.dumps(asdict(result)), flush=True)
    return result


def execute(lifecycle: Lifecycle) -> int:
    parser = argparse.ArgumentParser(
        description="Run real HIP workloads in fresh cosim vHosts"
    )
    parser.add_argument("output", type=Path)
    parser.add_argument("assets", type=Path)
    launcher_default = Path(
        os.environ.get("CARGO_TARGET_DIR", "build/cargo/host")
    ) / "release/cosim"
    parser.add_argument("--launcher", type=Path, default=launcher_default)
    parser.add_argument("--gem5", type=Path, required=True)
    parser.add_argument("--qemu", type=Path)
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--boot-timeout", type=int, default=300)
    parser.add_argument("--test-timeout", type=int, default=300)
    parser.add_argument("--memory", default=Inputs.memory)
    parser.add_argument("--vram", default=Inputs.vram)
    parser.add_argument("--cpus", type=int, default=Inputs.cpus)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    try:
        recipe, _, _ = load_regression(args.recipe)
        args.qemu = args.qemu or qemu_binary(ROOT, recipe.architecture)
        if args.qemu is None:
            raise ValueError("matching QEMU is missing; run just ci-build-qemu")
        inputs = Inputs(*(getattr(args, name).resolve() for name in
                          ("output", "assets", "launcher", "gem5", "qemu")),
                        args.recipe, args.boot_timeout, args.test_timeout,
                        args.memory, args.vram, args.cpus)
        if inputs.boot_timeout <= 0 or inputs.test_timeout <= 0:
            raise ValueError("timeouts must be positive")
        if inputs.cpus <= 0:
            raise ValueError("cpus must be positive")
        prepare(inputs)
        lifecycle.check()
        with (inputs.output / "matrix.tsv").open("w", newline="") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=list(asdict(Result(""))), delimiter="\t"
            )
            writer.writeheader()
            for program in PROGRAMS:
                lifecycle.check()
                result = run_case(inputs, program, lifecycle)
                results.append(result)
                writer.writerow(asdict(result))
                stream.flush()
                if result.status != "PASS":
                    break
        lifecycle.check()
        passed = len(results) == len(PROGRAMS) and all(
            row.status == "PASS" for row in results
        )
        write_json(inputs.output / "verdict.json", {
            "status": "PASS" if passed else "FAIL",
            "expected_programs": PROGRAMS,
            "results": [asdict(row) for row in results],
        })
        return 0 if passed else 1
    except (
        OSError, ValueError, RuntimeError, subprocess.CalledProcessError
    ) as error:
        write_json(args.output / "verdict.json", {
            "status": "FAIL", "reason": str(error),
        })
        print(str(error), flush=True)
        return 1


if __name__ == "__main__":
    input_fd = (
        sys.stdin.fileno()
        if os.environ.get("COSIM_STDIN_LIFELINE") == "1" else None
    )
    with Lifecycle(input_fd).installed() as lifecycle:
        raise SystemExit(execute(lifecycle))

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

from guest_console import GuestConsole
from ci_lifecycle import Lifecycle
from runtime_artifact import ROOT, sha256

sys.path.insert(0, str(ROOT))
from resources.images.bundle import verify_bundle
from resources.images.recipe import load_recipe


PROGRAMS = (
    "vector_add", "gemm", "reduction", "transpose", "prefix_scan", "histogram"
)
VHOST_REGRESSION_SCRIPT = "/usr/local/bin/cosim-rocm-regression.sh"
MI455X_RECIPE = "ubuntu/24.04/x86_64/rocm/10.3"
MI455X_REGRESSION_SCRIPT = ROOT / "scripts/ci/run_rocm_mi455x.sh"


@dataclass(frozen=True)
class Inputs:
    output: Path
    assets: Path
    launcher: Path
    simulator: Path
    qemu: Path
    boot_timeout: int
    test_timeout: int
    memory: str = "4G"
    vram: str = "4G"
    cpus: int = 2
    backend: str = "gem5"


@dataclass
class Result:
    program: str
    status: str = "FAIL"
    reason: str = "execution incomplete"
    elapsed_seconds: float = 0


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def prepare(inputs: Inputs) -> dict:
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise RuntimeError("the ROCm vHost requires Linux x86_64 with KVM")
    with Path("/dev/kvm").open("rb+"):
        pass
    if inputs.backend == "rocjitsu":
        recipe = load_recipe(ROOT, MI455X_RECIPE)
        metadata = verify_bundle(ROOT, recipe, inputs.assets, use_stamp=True)
        device = ROOT / "resources/devices/gpu/mi455x/device.toml"
        with device.open("rb") as file:
            rom = ROOT / tomllib.load(file)["pci"]["rom"]
    else:
        metadata = json.loads((inputs.assets / "manifest.json").read_text())
        for name in ("kernel", "disk"):
            if (
                sha256(inputs.assets / name)
                != metadata["files"][name]["sha256"]
            ):
                raise ValueError(f"vHost asset checksum mismatch: {name}")
        rom = (
            ROOT
            / "third_party/gem5-resources/src/x86-ubuntu-gpu-ml/files/mi300.rom"
        )
    provenance = {"assets": metadata, "binaries": {}, "sources": {}}
    for path in (inputs.launcher, inputs.simulator, inputs.qemu):
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError(f"missing executable: {path}")
        provenance["binaries"][str(path)] = sha256(path)
    provenance["firmware"] = {str(rom): sha256(rom)}
    patch_dir = inputs.output / "patch"
    patch_dir.mkdir()
    repositories = [("project", ROOT)]
    qemu_source = ROOT / "third_party/qemu"
    if inputs.backend == "gem5" or (qemu_source / ".git").exists():
        repositories.append(("qemu", qemu_source))
    else:
        gitlink = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD:third_party/qemu"],
            text=True,
        ).strip()
        provenance["sources"]["qemu"] = {"gitlink_commit": gitlink}
    if inputs.backend == "gem5":
        repositories.extend((
            ("gem5", ROOT / "third_party/gem5"),
            ("gem5-resources", ROOT / "third_party/gem5-resources"),
        ))
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


def topology(inputs: Inputs, share: Path, disk_format: str = "qcow2") -> dict:
    vhost = {
        "runtime": {"binary": str(inputs.qemu)},
        "memory": inputs.memory, "cpus": inputs.cpus,
        "args": [
            "-virtfs", "local,path=" + str(share).replace(",", ",,")
            + ",mount_tag=cosimci,security_model=none,readonly=on",
        ],
    }
    device = {"id": "gpu"}
    machine = {"id": "m0", "vhost": vhost, "devices": [device]}
    if inputs.backend == "rocjitsu":
        imports = ("machines/ubuntu-mi455x.yaml",)
        machine["use"] = "ubuntu-mi455x"
        vhost.update({
            "image": None,
            "disks": [{
                "id": "root", "backing": str(inputs.assets / "disk"),
                "format": disk_format, "bus": "virtio", "boot": True,
            }],
        })
        device.update({
            "use": "mi455x",
            "runtime": {"env": {"ROCJITSU_BINARY": str(inputs.simulator)}},
        })
    else:
        imports = ("vhosts/qemu.yaml", "devices/gpu/mi300x/gem5.yaml")
        vhost["use"] = "vhost-x86-rocm"
        device.update({
            "use": "mi300x",
            "runtime": {"binary": str(inputs.simulator)},
            "memory_regions": [{
                "name": "vram", "size": inputs.vram, "align": "2M",
            }],
        })
    return {
        "version": 1,
        "imports": [str(ROOT / "resources" / path) for path in imports],
        "machines": [machine],
    }


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
    stream: socket.socket, row: Path, inputs: Inputs, program: str,
    vhost_script: str,
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
            f"bash {shlex.quote(vhost_script)} "
            f"{shlex.quote(program)} {inputs.test_timeout}",
            inputs.test_timeout + 600,
        )
        name = "gemm_tiled" if program == "gemm" else program
        outcome.require_workload(name)
        if b"[COSIM_ENV] HSA_ENABLE_INTERRUPT=0" not in outcome.output:
            raise RuntimeError("vHost environment was not confirmed")
        if inputs.backend == "rocjitsu":
            if b"[COSIM_ENV] HSA_ENABLE_SDMA=unset" not in outcome.output:
                raise RuntimeError("vHost SDMA environment was not confirmed")
            transport.sendline(b"systemctl poweroff")
            transport.expect(pexpect.EOF, timeout=60)


def verify_cleanup(session: Path) -> None:
    manifest = json.loads((session / "manifest.json").read_text())
    paths = [
        *manifest["endpoints"], *manifest["pools"], *manifest["overlays"],
        manifest["layout"]["pool_dir"],
    ]
    remaining = [path for path in paths if os.path.lexists(path)]
    if remaining:
        raise RuntimeError(f"session resources remain: {remaining}")


def run_case(
    inputs: Inputs, program: str, lifecycle: Lifecycle, disk_format: str
) -> Result:
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
    source = ROOT / "tests/kernels" / f"{program}.cpp"
    vhost_script = VHOST_REGRESSION_SCRIPT
    vhost_environment = {"HSA_ENABLE_INTERRUPT": "0"}
    if inputs.backend == "rocjitsu":
        vhost_environment["HSA_ENABLE_SDMA"] = None
        shutil.copy2(MI455X_REGRESSION_SCRIPT, share)
        vhost_script = f"/mnt/cosim-ci/{MI455X_REGRESSION_SCRIPT.name}"
    config = row / "topology.yaml"
    config.write_text(yaml.safe_dump(topology(inputs, share, disk_format)))
    command = [
        str(inputs.launcher), "run", str(config),
        "--run-dir", str(session),
        "--ready-timeout", str(inputs.boot_timeout), "--stdin-lifeline",
    ]
    write_json(row / "run-manifest.json", {
        "program": str(source.relative_to(ROOT)),
        "source_sha256": sha256(source), "mode": "pure_test", "repeat": 1,
        "vhost_environment": vhost_environment,
        "boot_timeout": inputs.boot_timeout,
        "test_timeout": inputs.test_timeout,
        "artifact_dir": str(row), "command": command,
        f"{inputs.backend}_binary": str(inputs.simulator),
        "vhost_script": vhost_script,
        "runner_argument": program,
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
                        exercise_vhost(
                            stream, row, inputs, program, vhost_script
                        )
                    if inputs.backend == "rocjitsu":
                        try:
                            process.wait(timeout=60)
                        except subprocess.TimeoutExpired as error:
                            raise RuntimeError(
                                "vHost poweroff timed out"
                            ) from error
                    lifecycle.check()
                finally:
                    stop(process, session)
        if inputs.backend == "rocjitsu":
            verify_cleanup(session)
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
    parser.add_argument(
        "--backend", choices=("gem5", "rocjitsu"), default="gem5"
    )
    parser.add_argument("--gem5", type=Path)
    parser.add_argument("--rocjitsu", type=Path)
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--boot-timeout", type=int, default=300)
    parser.add_argument("--test-timeout", type=int, default=300)
    parser.add_argument("--memory", default=Inputs.memory)
    parser.add_argument("--vram", default=Inputs.vram)
    parser.add_argument("--cpus", type=int, default=Inputs.cpus)
    args = parser.parse_args()
    if args.backend == "gem5":
        if args.gem5 is None:
            parser.error("--gem5 is required with the gem5 backend")
        if args.rocjitsu is not None:
            parser.error("--rocjitsu requires --backend rocjitsu")
        simulator = args.gem5
    else:
        simulator = (
            args.rocjitsu or ROOT / "build/rocjitsu/x86_64/Release/rocjitsu"
        )
    inputs = Inputs(
        output=args.output.resolve(), assets=args.assets.resolve(),
        launcher=args.launcher.resolve(),
        simulator=simulator.resolve(),
        qemu=args.qemu.resolve(),
        boot_timeout=args.boot_timeout, test_timeout=args.test_timeout,
        memory=args.memory, vram=args.vram, cpus=args.cpus,
        backend=args.backend,
    )
    inputs.output.mkdir(parents=True, exist_ok=False)
    results = []
    try:
        if inputs.boot_timeout <= 0 or inputs.test_timeout <= 0:
            raise ValueError("timeouts must be positive")
        if inputs.cpus <= 0:
            raise ValueError("cpus must be positive")
        metadata = prepare(inputs)
        disk_format = metadata.get("disk_format", "qcow2")
        lifecycle.check()
        with (inputs.output / "matrix.tsv").open("w", newline="") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=list(asdict(Result(""))), delimiter="\t"
            )
            writer.writeheader()
            for program in PROGRAMS:
                lifecycle.check()
                result = run_case(inputs, program, lifecycle, disk_format)
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
        write_json(inputs.output / "verdict.json", {
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

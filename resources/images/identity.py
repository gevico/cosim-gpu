# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path
import shutil
import subprocess
import sys
from dataclasses import replace

from .errors import ImageError
from .fingerprint import digest_json, sha256_file
from .recipe import ImageRecipe
from .toolchain import (
    ANSIBLE_REQUIREMENTS,
    PACKER_ROOT,
    ANSIBLE_CORE_VERSION,
    PACKER_VERSION,
    Toolchain,
)


def input_fingerprint(
    workspace: Path,
    recipe: ImageRecipe,
    tools: Toolchain,
) -> dict:
    files = input_files(workspace, recipe)
    file_hashes = {
        path.relative_to(workspace).as_posix(): sha256_file(path)
        for path in files
    }
    inputs = {
        "schema": 1,
        "recipe": recipe.identifier,
        "base": {
            "url": recipe.base_url,
            "sha256": recipe.base_sha256,
            "format": recipe.base_format,
        },
        "files": file_hashes,
        "toolchain": {
            "packer": PACKER_VERSION,
            "ansible_core": ANSIBLE_CORE_VERSION,
            "qemu": tools.qemu_version,
            "qemu_architecture": tools.qemu_architecture,
            "qemu_sha256": tools.qemu_sha256,
            "qemu_img": tools.qemu_img_version,
            "qemu_img_sha256": tools.qemu_img_sha256,
            "python": sys.version.split()[0],
        },
        "epoch": os.environ.get("COSIM_ROCM_IMAGE_EPOCH", "1"),
    }
    return {"inputs": inputs, "input_key": digest_json(inputs)}


def input_files(workspace: Path, recipe: ImageRecipe) -> list[Path]:
    files = [path for _, path in _input_candidates(workspace, recipe)]
    for path in files:
        resolved = path.resolve()
        if not resolved.is_relative_to(workspace):
            raise ImageError(f"image input escapes workspace: {path}")
        if not resolved.is_file():
            raise ImageError(f"missing image input: {path}")
    return sorted(set(path.resolve() for path in files))


def reusable_input_issues(
    workspace: Path,
    recipe: ImageRecipe,
    stored: object,
) -> list[str]:
    if not isinstance(stored, dict):
        return ["image manifest has no input record"]
    issues = []
    if stored.get("schema") != 1 or stored.get("recipe") != recipe.identifier:
        issues.append("recipe identity changed")
    expected_base = {
        "url": recipe.base_url,
        "sha256": recipe.base_sha256,
        "format": recipe.base_format,
    }
    if stored.get("base") != expected_base:
        issues.append("base image identity changed")
    if stored.get("epoch") != os.environ.get("COSIM_ROCM_IMAGE_EPOCH", "1"):
        issues.append("image build epoch changed")
    toolchain = stored.get("toolchain")
    if (
        not isinstance(toolchain, dict)
        or toolchain.get("packer") != PACKER_VERSION
        or toolchain.get("ansible_core") != ANSIBLE_CORE_VERSION
    ):
        issues.append("pinned image provisioning tool versions changed")
    stored_files = stored.get("files")
    if not isinstance(stored_files, dict):
        return issues + ["image manifest has no input file hashes"]
    current_files = set()
    for name, path in _input_candidates(workspace, recipe):
        resolved = path.resolve()
        if not resolved.is_relative_to(workspace):
            issues.append(f"image input escapes workspace ({name}): {path}")
            continue
        relative = resolved.relative_to(workspace).as_posix()
        current_files.add(relative)
        if not resolved.is_file():
            issues.append(f"missing image input ({name}): {path}")
            continue
        expected_hash = stored_files.get(relative)
        if expected_hash != sha256_file(resolved):
            issues.append(f"image input changed: {relative}")
    for removed in sorted(set(stored_files) - current_files):
        issues.append(f"image input removed: {removed}")
    return issues


def _input_candidates(
    workspace: Path,
    recipe: ImageRecipe,
) -> list[tuple[str, Path]]:
    shared_directories = [workspace / PACKER_ROOT]
    candidates = [
        (path.relative_to(workspace).as_posix(), path)
        for directory in shared_directories
        for path in directory.rglob("*")
        if path.is_file()
    ]
    candidates.extend([
        ("resources/images/requirements.txt", workspace / ANSIBLE_REQUIREMENTS),
        (
            "resources/images/builder.py",
            workspace / "resources/images/builder.py",
        ),
        (
            "resources/images/recipe.py",
            workspace / "resources/images/recipe.py",
        ),
        (
            "resources/images/process.py",
            workspace / "resources/images/process.py",
        ),
        (
            "resources/images/toolchain.py",
            workspace / "resources/images/toolchain.py",
        ),
        (
            "resources/images/bundle.py",
            workspace / "resources/images/bundle.py",
        ),
        (
            "resources/images/errors.py",
            workspace / "resources/images/errors.py",
        ),
        (
            "resources/images/fingerprint.py",
            workspace / "resources/images/fingerprint.py",
        ),
        (
            "resources/images/identity.py",
            workspace / "resources/images/identity.py",
        ),
        ("resources/images/cli.py", workspace / "resources/images/cli.py"),
        *recipe_source_files(workspace, recipe),
        *recipe.provision_files.items(),
    ])
    return candidates


def missing_inputs(workspace: Path, recipe: ImageRecipe) -> list[str]:
    sources: list[tuple[str, Path]] = [
        ("Packer templates", workspace / PACKER_ROOT),
        ("Ansible requirements", workspace / ANSIBLE_REQUIREMENTS),
        ("image builder", workspace / "resources/images/builder.py"),
        ("recipe loader", workspace / "resources/images/recipe.py"),
        ("process runner", workspace / "resources/images/process.py"),
        ("toolchain manager", workspace / "resources/images/toolchain.py"),
        ("bundle manager", workspace / "resources/images/bundle.py"),
        ("image errors", workspace / "resources/images/errors.py"),
        ("fingerprint helper", workspace / "resources/images/fingerprint.py"),
        ("identity helper", workspace / "resources/images/identity.py"),
        ("image CLI", workspace / "resources/images/cli.py"),
        ("recipe playbook", recipe.playbook_file),
        ("recipe metadata", recipe.recipe_file),
        *recipe.provision_files.items(),
    ]
    missing = []
    for label, path in sources:
        if label == "Packer templates":
            if not path.is_dir():
                missing.append(f"{label}: {path}")
            elif not path.resolve().is_relative_to(workspace):
                missing.append(f"input escapes workspace ({label}): {path}")
            continue
        if not path.is_file():
            missing.append(f"{label}: {path}")
            continue
        if not path.resolve().is_relative_to(workspace):
            missing.append(f"input escapes workspace ({label}): {path}")
    return missing


def missing_recipe_files(workspace: Path, recipe: ImageRecipe) -> list[str]:
    names = [
        "resources/images/builder.py",
        "resources/images/recipe.py",
        "resources/images/process.py",
        "resources/images/toolchain.py",
        "resources/images/bundle.py",
        "resources/images/errors.py",
        "resources/images/fingerprint.py",
        "resources/images/identity.py",
        "resources/images/cli.py",
    ]
    paths = [
        workspace / PACKER_ROOT / "qemu.pkr.hcl",
        workspace / ANSIBLE_REQUIREMENTS,
        recipe.recipe_file,
        recipe.playbook_file,
        *(workspace / name for name in names),
    ]
    return [str(path) for path in paths if not path.is_file()]


def recipe_source_files(
    workspace: Path,
    recipe: ImageRecipe,
) -> list[tuple[str, Path]]:
    relative_directory = recipe.directory.relative_to(workspace)
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={workspace.resolve()}",
            "-C",
            str(workspace),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            relative_directory.as_posix(),
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip()
        raise ImageError(f"cannot enumerate image recipe files: {detail}")
    paths = [
        Path(os.fsdecode(name))
        for name in result.stdout.split(b"\0")
        if name
    ]
    return [
        (path.as_posix(), workspace / path)
        for path in sorted(paths)
        if (workspace / path).is_file()
    ]


def stage_recipe(
    workspace: Path,
    recipe: ImageRecipe,
    destination: Path,
) -> ImageRecipe:
    workspace = workspace.resolve()
    recipe_root = recipe.directory.relative_to(workspace)
    staged_directory = destination / recipe.identifier
    shutil.rmtree(staged_directory, ignore_errors=True)
    staged_directory.mkdir(parents=True)
    for name, source in recipe_source_files(workspace, recipe):
        relative = Path(name).relative_to(recipe_root)
        target = staged_directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    def staged_path(path: Path) -> Path:
        resolved = path.resolve()
        if resolved.is_relative_to(recipe.directory):
            return staged_directory / resolved.relative_to(recipe.directory)
        return path

    return replace(
        recipe,
        directory=staged_directory.resolve(),
        recipe_file=staged_path(recipe.recipe_file),
        playbook_file=staged_path(recipe.playbook_file),
        provision_files={
            name: staged_path(path)
            for name, path in recipe.provision_files.items()
        },
    )

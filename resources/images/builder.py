# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
import json
import os
import platform
import shutil
import sys
import uuid

from .bundle import (
    exclusive_lock,
    mark_verified_bundle,
    packer_disk_output,
    recipe_lock_key,
    publish,
    verify_bundle,
    write_manifest,
)
from .errors import ImageError
from .identity import (
    input_fingerprint,
    missing_inputs,
    missing_recipe_files,
    reusable_input_issues,
    stage_recipe,
)
from .process import run_logged
from .recipe import ImageRecipe, load_recipe
from .toolchain import (
    PACKER_ROOT,
    ensure_ansible,
    ensure_packer,
    inspect_toolchain,
    packer_variables,
    create_temporary_ssh_keypair,
    tool_environment,
    validate_ansible,
)


def inspect_recipe(
    workspace: Path,
    identifier: str,
    *,
    cache_verification: bool = False,
) -> dict:
    root = workspace.resolve()
    recipe = load_recipe(root, identifier)
    output = recipe.output_path(root)
    fingerprint = None
    status = "build-required"
    reasons: list[str] = []
    cached_manifest = None
    if output.exists() or output.is_symlink():
        try:
            cached_manifest = verify_bundle(
                root,
                recipe,
                output,
                use_stamp=True,
                write_stamp=cache_verification,
            )
            reasons.extend(
                reusable_input_issues(root, recipe, cached_manifest["inputs"])
            )
            status = "rebuild-required" if reasons else "ready"
        except (OSError, ValueError, ImageError) as error:
            status = "rebuild-required"
            reasons.append(str(error))
    if status != "ready":
        missing = missing_inputs(root, recipe)
        tools, missing_tools = inspect_toolchain(root, recipe)
        missing.extend(missing_tools)
        if missing:
            status = "blocked"
            reasons.extend(missing)
        elif tools is not None:
            fingerprint = input_fingerprint(root, recipe, tools)
    if status == "ready" and cached_manifest is not None:
        fingerprint = {
            "input_key": cached_manifest["input_key"],
            "inputs": cached_manifest["inputs"],
        }
    return {
        "recipe": {
            "id": recipe.identifier,
            "distribution": recipe.distribution,
            "release": recipe.release,
            "architecture": recipe.architecture,
            "software": recipe.software,
            "software_release": recipe.software_release,
        },
        "status": status,
        "input_key": fingerprint["input_key"] if fingerprint else None,
        "inputs": fingerprint["inputs"] if fingerprint else None,
        "artifact_directory": str(output),
        "disk": str(output / "disk"),
        "disk_format": recipe.disk_format,
        "kernel": (
            str(output / recipe.kernel_file)
            if recipe.kernel_file else None
        ),
        "reasons": reasons,
        "commands": [
            ["scripts/host/cosim-image", "validate", recipe.identifier],
            ["scripts/host/cosim-image", "build", recipe.identifier],
        ],
    }


def recipe_fingerprint(workspace: Path, identifier: str) -> dict:
    root = workspace.resolve()
    recipe = load_recipe(root, identifier)
    missing = missing_inputs(root, recipe)
    tools, missing_tools = inspect_toolchain(root, recipe)
    missing.extend(missing_tools)
    if missing or tools is None:
        raise ImageError(
            "image build inputs are unavailable: " + "; ".join(missing)
        )
    return input_fingerprint(root, recipe, tools)


def validate_recipe(
    workspace: Path,
    identifier: str,
    *,
    syntax_only: bool = False,
) -> None:
    root = workspace.resolve()
    recipe = load_recipe(root, identifier)
    if syntax_only:
        packer, ansible = _ensure_toolchain(root)
        run_logged(
            [str(packer), "validate", "-syntax-only", str(root / PACKER_ROOT)],
            root,
            tool_environment(root),
            root / "build/logs/packer-syntax.log",
        )
        validate_ansible(root, recipe, ansible)
        print(f"Recipe is valid: {recipe.identifier}")
        return
    missing = missing_recipe_files(root, recipe)
    if missing:
        raise ImageError(
            "image recipe files are unavailable: " + "; ".join(missing)
        )
    packer, ansible = _ensure_toolchain(root)
    environment = tool_environment(root)
    tools, missing_tools = inspect_toolchain(
        root,
        recipe,
        require_kernel_tools=False,
    )
    if missing_tools or tools is None:
        message = "; ".join(missing_tools)
        raise ImageError(
            "image validation tools are unavailable: " + message
        )
    validate_stage = root / "build/images/.validate"
    variable_file = root / "build/images/.validate.pkrvars.json"
    variable_file.parent.mkdir(parents=True, exist_ok=True)
    staged_recipe = stage_recipe(root, recipe, validate_stage / "recipe")
    key_directory, private_key, public_key = create_temporary_ssh_keypair(root)
    try:
        variables = packer_variables(
            staged_recipe,
            validate_stage,
            tools,
            ansible,
            validate_stage / "fetched",
            validate_stage / "ansible-tmp",
            ssh_private_key_file=private_key,
            ssh_public_key=public_key,
        )
        variable_file.write_text(
            json.dumps(variables, indent=2) + "\n",
            encoding="utf-8",
        )
    except BaseException:
        shutil.rmtree(key_directory, ignore_errors=True)
        raise
    try:
        run_logged(
            [str(packer), "init", str(root / PACKER_ROOT)],
            root,
            environment,
            root / "build/logs/packer-init.log",
        )
        run_logged(
            [
                str(packer),
                "validate",
                "-var-file",
                str(variable_file),
                str(root / PACKER_ROOT),
            ],
            root,
            environment,
            root / "build/logs/packer-validate.log",
        )
        validate_ansible(root, staged_recipe, ansible)
    finally:
        variable_file.unlink(missing_ok=True)
        shutil.rmtree(key_directory, ignore_errors=True)
    print(f"Packer and Ansible configuration is valid: {recipe.identifier}")


def build_recipe(workspace: Path, identifier: str) -> dict:
    root = workspace.resolve()
    recipe = load_recipe(root, identifier)
    missing = missing_inputs(root, recipe)
    if missing:
        raise ImageError(
            "image build inputs are unavailable: " + "; ".join(missing)
        )
    _require_accelerator(recipe)
    packer, ansible = _ensure_toolchain(root)
    tools, missing_tools = inspect_toolchain(root, recipe)
    if missing_tools or tools is None:
        raise ImageError(
            "image build tools are unavailable: " + "; ".join(missing_tools)
        )
    fingerprint = input_fingerprint(root, recipe, tools)
    output = recipe.output_path(root)
    lock_path = (
        root / "build/images/.locks" / f"{recipe_lock_key(identifier)}.lock"
    )
    with exclusive_lock(lock_path):
        if output.exists():
            try:
                manifest = verify_bundle(
                    root,
                    recipe,
                    output,
                    fingerprint["input_key"],
                    use_stamp=True,
                )
                print(f"Reusing verified image bundle: {output}")
                return {
                    "status": "ready",
                    "input_key": manifest["input_key"],
                    "artifact_directory": str(output),
                }
            except (OSError, ValueError, ImageError) as error:
                print(f"Rebuilding image bundle: {error}", file=sys.stderr)
        output.parent.mkdir(parents=True, exist_ok=True)
        stage = output.parent / f"build-{output.name}-{uuid.uuid4().hex}"
        stage.mkdir()
        fetched = stage / "fetched"
        packer_output = stage / "packer-output"
        ansible_temp = stage / "ansible-tmp"
        fetched.mkdir()
        ansible_temp.mkdir()
        logs = stage / "logs"
        logs.mkdir()
        staged_recipe = stage_recipe(root, recipe, stage / "recipe")
        environment = tool_environment(root)
        key_directory, private_key, public_key = create_temporary_ssh_keypair(
            root
        )
        try:
            variables = packer_variables(
                staged_recipe,
                stage,
                tools,
                ansible,
                fetched,
                ansible_temp,
                ssh_private_key_file=private_key,
                ssh_public_key=public_key,
            )
            variable_file = stage / "recipe.pkrvars.json"
            variable_file.write_text(
                json.dumps(variables, indent=2) + "\n",
                encoding="utf-8",
            )
        except BaseException:
            shutil.rmtree(key_directory, ignore_errors=True)
            raise
        environment.update({
            "PACKER_LOG": "1",
            "PACKER_LOG_PATH": str(logs / "packer.log"),
        })
        try:
            run_logged(
                [str(packer), "init", str(root / PACKER_ROOT)],
                root,
                environment,
                logs / "packer-init.log",
            )
            run_logged(
                [
                    str(packer),
                    "validate",
                    "-var-file",
                    str(variable_file),
                    str(root / PACKER_ROOT),
                ],
                root,
                environment,
                logs / "packer-validate.log",
            )
            run_logged(
                [
                    str(packer),
                    "build",
                    "-color=false",
                    "-var-file",
                    str(variable_file),
                    str(root / PACKER_ROOT),
                ],
                root,
                environment,
                logs / "packer-build.log",
            )
            products = stage / "products"
            products.mkdir()
            disk_image = packer_disk_output(packer_output, recipe.image_name)
            os.replace(disk_image, products / "disk")
            for result_file in recipe.result_files:
                fetched_path = fetched / result_file.name
                if not fetched_path.is_file():
                    raise ImageError(
                        "Packer did not fetch declared result file "
                        f"{result_file.name}"
                    )
                os.replace(fetched_path, products / result_file.name)
            shutil.copy2(logs / "packer.log", products / "packer.log")
            shutil.copy2(logs / "packer-build.log", products / "build.log")
            manifest = write_manifest(recipe, fingerprint, products)
            verify_bundle(root, recipe, products, fingerprint["input_key"])
            publish(products, output)
            mark_verified_bundle(root, recipe, output, manifest)
            shutil.rmtree(stage)
            print(f"Built and verified image bundle: {output}")
            return {
                "status": "built",
                "input_key": manifest["input_key"],
                "artifact_directory": str(output),
            }
        except BaseException:
            print(
                "Image build staging directory retained for diagnostics: "
                f"{stage}",
                file=sys.stderr,
            )
            raise
        finally:
            shutil.rmtree(key_directory, ignore_errors=True)


def verify_recipe(
    workspace: Path,
    identifier: str,
    expected_key: str | None = None,
) -> dict:
    root = workspace.resolve()
    recipe = load_recipe(root, identifier)
    return verify_bundle(root, recipe, recipe.output_path(root), expected_key)


def _require_accelerator(recipe: ImageRecipe) -> None:
    system = platform.system()
    host_architecture = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "aarch64": "aarch64",
        "arm64": "aarch64",
        "riscv64": "riscv64",
    }.get(platform.machine().lower())
    if recipe.accelerator == "kvm":
        if system != "Linux" or host_architecture != recipe.architecture:
            raise ImageError(
                f"recipe {recipe.identifier} requires Linux KVM "
                f"on {recipe.architecture}"
            )
        if not Path("/dev/kvm").exists():
            raise ImageError("the selected image recipe requires /dev/kvm")
    elif recipe.accelerator == "hvf":
        if system != "Darwin" or host_architecture != recipe.architecture:
            raise ImageError(
                f"recipe {recipe.identifier} requires macOS "
                "Hypervisor.framework on "
                f"{recipe.architecture}"
            )
    elif recipe.accelerator != "tcg":
        raise ImageError(
            f"unsupported image builder accelerator: {recipe.accelerator}"
        )


def _ensure_toolchain(root: Path) -> tuple[Path, Path]:
    lock = root / "build/images/.locks/toolchain.lock"
    with exclusive_lock(lock):
        packer = ensure_packer(root)
        ansible = ensure_ansible(root)
    return packer, ansible

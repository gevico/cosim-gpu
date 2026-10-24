# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import tomllib

RESERVED_OUTPUT_NAMES = {"disk", "manifest.json", "packer.log", "build.log"}


class RecipeError(ValueError):
    pass


@dataclass(frozen=True)
class ResultFile:
    name: str
    guest_path: str


@dataclass(frozen=True)
class ImageRecipe:
    identifier: str
    directory: Path
    recipe_file: Path
    distribution: str
    release: str
    architecture: str
    software: str
    software_release: str
    base_url: str
    base_sha256: str
    base_format: str
    image_name: str
    disk_size: str
    disk_format: str
    cpus: int
    memory_mb: int
    ssh_username: str
    accelerator: str
    machine_type: str
    cpu_model: str
    playbook_file: Path
    variables: dict[str, str]
    result_files: tuple[ResultFile, ...]
    kernel_file: str | None
    provision_files: dict[str, Path]

    def output_path(self, workspace: Path) -> Path:
        return workspace / "build" / "images" / self.identifier


def list_recipes(workspace: Path) -> list[str]:
    recipes = workspace / "resources/images/recipes"
    if not recipes.is_dir():
        return []
    return sorted(
        path.relative_to(recipes).parent.as_posix()
        for path in recipes.rglob("recipe.toml")
        if path.is_file()
    )


def load_recipe(workspace: Path, identifier: str) -> ImageRecipe:
    safe_identifier = _relative_path(identifier, "recipe id")
    if len(safe_identifier.parts) != 5:
        raise RecipeError(
            "recipe id must have five path components: "
            "distribution/release/architecture/software/software-release"
        )
    (
        distribution,
        release,
        architecture,
        software,
        software_release,
    ) = safe_identifier.parts
    if architecture not in {"x86_64", "aarch64", "riscv64"}:
        raise RecipeError(
            f"unsupported recipe architecture {architecture!r}"
        )
    recipe_file = workspace / "resources/images/recipes" / safe_identifier
    recipe_file = recipe_file / "recipe.toml"
    if not recipe_file.is_file():
        raise RecipeError(f"image recipe not found: {identifier}")
    try:
        data = tomllib.loads(recipe_file.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise RecipeError(
            f"cannot read image recipe {recipe_file}: {error}"
        ) from error
    if not isinstance(data, dict):
        raise RecipeError(
            f"image recipe must be a TOML table: {recipe_file}"
        )
    _require(data, "schema", int)
    if data["schema"] != 2:
        raise RecipeError(f"unsupported recipe schema {data['schema']}")
    _only(data, {"schema", "base", "provision", "result"}, "recipe")

    base = _mapping(data, "base")
    _only(base, {"url", "sha256", "format"}, "base")
    _require(base, "url", str)
    _require(base, "sha256", str)
    _require(base, "format", str)
    if not base["url"].startswith("https://"):
        raise RecipeError("base.url must use HTTPS")
    if not re.fullmatch(r"[0-9a-f]{64}", base["sha256"]):
        raise RecipeError("base.sha256 must be a lowercase SHA-256 digest")
    if base["format"] not in {"raw", "qcow2"}:
        raise RecipeError("base.format must be raw or qcow2")

    provision = _mapping(data, "provision")
    _only(
        provision,
        {
            "image_name",
            "disk_size",
            "disk_format",
            "cpus",
            "memory_mb",
            "ssh_username",
            "accelerator",
            "machine_type",
            "cpu_model",
            "playbook",
            "variables",
            "files",
        },
        "provision",
    )
    for key in (
        "image_name", "disk_size", "disk_format", "ssh_username", "accelerator",
        "machine_type", "cpu_model", "playbook",
    ):
        _require(provision, key, str)
    for key in ("cpus", "memory_mb"):
        _require(provision, key, int)
    if provision["disk_format"] not in {"raw", "qcow2"}:
        raise RecipeError("provision.disk_format must be raw or qcow2")
    if provision["cpus"] < 1 or provision["memory_mb"] < 512:
        raise RecipeError("provision CPU and memory values are out of range")
    if provision["accelerator"] not in {"kvm", "tcg", "hvf"}:
        raise RecipeError("provision.accelerator must be kvm, tcg or hvf")

    variables = _mapping(provision, "variables")
    if not all(
        isinstance(name, str) and isinstance(value, str)
        for name, value in variables.items()
    ):
        raise RecipeError("provision.variables must map names to strings")
    provision_files_data = _mapping(provision, "files")
    provision_files = {
        name: workspace / _relative_path(path, f"provision.files.{name}")
        for name, path in provision_files_data.items()
        if isinstance(name, str) and isinstance(path, str)
    }
    if len(provision_files) != len(provision_files_data):
        raise RecipeError(
            "provision.files must map names to workspace-relative paths"
        )

    result = _mapping(data, "result")
    _only(result, {"kernel", "files"}, "result")
    kernel_file = result.get("kernel")
    if kernel_file is not None and not isinstance(kernel_file, str):
        raise RecipeError("result.kernel must be a string or null")
    result_files_data = result.get("files", [])
    if not isinstance(result_files_data, list):
        raise RecipeError("result.files must be an array")
    result_files: list[ResultFile] = []
    for index, item in enumerate(result_files_data):
        if not isinstance(item, dict):
            raise RecipeError(
                f"result.files[{index}] must be an object"
            )
        _only(item, {"name", "guest_path"}, f"result.files[{index}]")
        _require(item, "name", str)
        _require(item, "guest_path", str)
        name = item["name"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise RecipeError(f"invalid artifact name {name!r}")
        if name in RESERVED_OUTPUT_NAMES:
            raise RecipeError(
                f"result.files[{index}].name is reserved: {name}"
            )
        guest_path = Path(item["guest_path"])
        if not guest_path.is_absolute() or ".." in guest_path.parts:
            raise RecipeError(
                f"artifact guest_path must be absolute: {guest_path}"
            )
        result_files.append(ResultFile(name, item["guest_path"]))
    result_names = {item.name for item in result_files}
    if len(result_names) != len(result_files):
        raise RecipeError("result.files names must be unique")
    if kernel_file is not None and kernel_file not in result_names:
        raise RecipeError(
            "result.kernel must name a declared result file"
        )

    recipe_directory = recipe_file.parent.resolve()
    playbook_file = _inside_directory(
        recipe_directory,
        provision["playbook"],
        "provision.playbook",
    )
    if not playbook_file.is_file():
        raise RecipeError(
            f"recipe Ansible playbook not found: {playbook_file}"
        )

    return ImageRecipe(
        identifier=identifier,
        directory=recipe_directory,
        recipe_file=recipe_file.resolve(),
        distribution=distribution,
        release=release,
        architecture=architecture,
        software=software,
        software_release=software_release,
        base_url=base["url"],
        base_sha256=base["sha256"],
        base_format=base["format"],
        image_name=provision["image_name"],
        disk_size=provision["disk_size"],
        disk_format=provision["disk_format"],
        cpus=provision["cpus"],
        memory_mb=provision["memory_mb"],
        ssh_username=provision["ssh_username"],
        accelerator=provision["accelerator"],
        machine_type=provision["machine_type"],
        cpu_model=provision["cpu_model"],
        playbook_file=playbook_file,
        variables=dict(variables),
        result_files=tuple(result_files),
        kernel_file=kernel_file,
        provision_files=provision_files,
    )


def _require(data: dict, key: str, expected: type) -> None:
    if key not in data or not isinstance(data[key], expected):
        raise RecipeError(f"recipe field {key!r} must be {expected.__name__}")


def _mapping(data: dict, key: str) -> dict:
    value = data.get(key)
    if not isinstance(value, dict):
        raise RecipeError(f"recipe field {key!r} must be an object")
    return value


def _only(data: dict, allowed: set[str], what: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise RecipeError(
            f"unknown {what} field{'s' if len(unknown) != 1 else ''}: "
            + ", ".join(unknown)
        )


def _relative_path(value: str, what: str) -> Path:
    path = PurePosixPath(value)
    if (
        "\\" in value
        or path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise RecipeError(f"{what} must be a safe relative path: {value!r}")
    return Path(*path.parts)


def _inside_directory(root: Path, value: str, what: str) -> Path:
    relative = _relative_path(value, what)
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise RecipeError(f"{what} escapes its recipe directory")
    return candidate

# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import tomllib


def relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError(f"expected a relative recipe path: {value!r}")
    return path


@dataclass(frozen=True)
class SimulatorRecipe:
    workspace: Path
    identifier: str
    directory: Path
    source: Path
    config: str
    binary: str
    entry: Path

    def output(self, architecture: str) -> str:
        if architecture not in {"x86_64", "aarch64"}:
            raise ValueError(
                f"unsupported simulator host architecture: {architecture}"
            )
        return f"build/{self.identifier}/{architecture}/{self.config}"

    def build_directory(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            try:
                path = path.relative_to(self.workspace)
            except ValueError as error:
                raise ValueError(
                    "simulator build directory must be under build/"
                ) from error
        relative(str(path))
        resolved = (self.workspace / path).resolve()
        root = (self.workspace / "build").resolve()
        if not resolved.is_relative_to(root) or resolved == root:
            raise ValueError("simulator build directory must be under build/")
        return resolved


def table(data: dict, name: str, fields: set[str]) -> dict:
    value = data.get(name)
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or any(
            not isinstance(item, str) or not item for item in value.values()
        )
    ):
        raise ValueError(
            f"invalid simulator recipe table {name}: expected {sorted(fields)}"
        )
    return value


def load_recipe(workspace: Path, identifier: str) -> SimulatorRecipe:
    workspace = workspace.resolve()
    name = relative(identifier)
    if len(name.parts) != 1:
        raise ValueError("simulator recipe must name one simulator")
    root = workspace / "resources/device_simulators"
    directory = (root / name).resolve()
    if not directory.is_relative_to(root.resolve()):
        raise ValueError("simulator recipe escapes its library")
    recipe_file = (directory / "recipe.toml").resolve()
    if not recipe_file.is_relative_to(directory):
        raise ValueError("simulator recipe escapes its directory")
    data = tomllib.loads(recipe_file.read_text())
    if (
        set(data) != {"schema", "source", "build", "runtime"}
        or type(data["schema"]) is not int
        or data["schema"] != 1
    ):
        raise ValueError("unsupported simulator recipe schema or fields")
    source = table(data, "source", {"path"})
    build = table(data, "build", {"config", "binary"})
    runtime = table(data, "runtime", {"entry"})
    source_path = workspace / relative(source["path"])
    entry_name = relative(runtime["entry"])
    if len(entry_name.parts) != 1:
        raise ValueError("simulator entry must be a filename")
    entry = (directory / entry_name).resolve()
    if len(relative(build["config"]).parts) != 1:
        raise ValueError("simulator build config must be a filename")
    if len(relative(build["binary"]).parts) != 1:
        raise ValueError("simulator binary must be a filename")
    if not source_path.resolve().is_relative_to(
        workspace
    ) or not entry.is_relative_to(directory):
        raise ValueError("simulator recipe input escapes its root")
    return SimulatorRecipe(
        workspace,
        identifier,
        directory,
        source_path,
        build["config"],
        build["binary"],
        entry,
    )

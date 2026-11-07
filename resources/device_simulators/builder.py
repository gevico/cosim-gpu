# SPDX-License-Identifier: Apache-2.0

"""Build simulator binaries from their tool recipes."""

import os
import subprocess

from .recipe import SimulatorRecipe


def build_recipe(
    recipe: SimulatorRecipe, output: str, jobs: int, scons_args: list[str]
) -> None:
    if jobs < 1:
        raise ValueError("build jobs must be positive")
    output = recipe.build_directory(output)
    scratch = output / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, TMPDIR=str(scratch))
    if not (output / "gem5.build/config").is_file():
        subprocess.run(
            [
                "scons",
                "defconfig",
                str(output),
                f"build_opts/{recipe.config}",
            ],
            cwd=recipe.source,
            env=environment,
            check=True,
        )
    subprocess.run(
        [
            "scons",
            str(output / recipe.binary),
            f"-j{jobs}",
            *scons_args,
        ],
        cwd=recipe.source,
        env=environment,
        check=True,
    )

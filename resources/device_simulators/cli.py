# SPDX-License-Identifier: Apache-2.0

"""Build and inspect device simulator recipes."""

import argparse
import json
from pathlib import Path
import subprocess

from .builder import build_recipe
from .recipe import load_recipe


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    value = sub.add_parser("value")
    value.add_argument("recipe")
    value.add_argument("field", choices=("config", "binary", "entry"))
    inspect = sub.add_parser("inspect")
    inspect.add_argument("recipe")
    build = sub.add_parser("build")
    build.add_argument("recipe")
    build.add_argument("output")
    build.add_argument("jobs", type=int)
    build.add_argument("scons_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[2]
    recipe = load_recipe(workspace, args.recipe)
    if args.operation == "value":
        print(getattr(recipe, args.field))
    elif args.operation == "inspect":
        print(
            json.dumps(
                {
                    "recipe": recipe.identifier,
                    "source": str(recipe.source),
                    "config": recipe.config,
                    "binary": recipe.binary,
                    "entry": str(recipe.entry),
                },
                indent=2,
            )
        )
    elif args.operation == "build":
        build_recipe(recipe, args.output, args.jobs, args.scons_args)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error

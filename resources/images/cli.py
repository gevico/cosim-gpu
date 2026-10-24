# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .builder import (
    build_recipe,
    inspect_recipe,
    recipe_fingerprint,
    validate_recipe,
    verify_recipe,
)
from .errors import ImageError
from .recipe import RecipeError, list_recipes, load_recipe


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build and verify vHost OS image recipes"
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(os.environ.get("COSIM_WORKSPACE", Path.cwd())),
    )
    commands = parser.add_subparsers(dest="operation", required=True)
    commands.add_parser("list", help="list available image recipes")
    inspect = commands.add_parser(
        "inspect",
        help="show recipe inputs and cache status",
    )
    inspect.add_argument("recipe")
    inspect.add_argument("--json", action="store_true")
    inspect.add_argument("--write-verification-cache", action="store_true")
    key = commands.add_parser("key", help="print the recipe build identity")
    key.add_argument("recipe")
    validate = commands.add_parser(
        "validate",
        help="validate the recipe and Packer configuration",
    )
    validate.add_argument("recipe")
    validate.add_argument("--syntax-only", action="store_true")
    build = commands.add_parser(
        "build",
        help="build or reuse a verified image bundle",
    )
    build.add_argument("recipe")
    verify = commands.add_parser(
        "verify",
        help="verify an existing image bundle",
    )
    verify.add_argument("recipe")
    verify.add_argument("--expected-key")
    arguments = parser.parse_args()
    workspace = arguments.workspace.resolve()
    try:
        if arguments.operation == "list":
            for identifier in list_recipes(workspace):
                recipe = load_recipe(workspace, identifier)
                print(
                    f"{identifier}\t{recipe.distribution} "
                    f"{recipe.release}\t{recipe.architecture}\t"
                    f"{recipe.software} {recipe.software_release}"
                )
        elif arguments.operation == "inspect":
            state = inspect_recipe(
                workspace,
                arguments.recipe,
                cache_verification=arguments.write_verification_cache,
            )
            if arguments.json:
                print(json.dumps(state, sort_keys=True))
            else:
                print(json.dumps(state, indent=2, sort_keys=True))
        elif arguments.operation == "key":
            print(
                recipe_fingerprint(workspace, arguments.recipe)["input_key"]
            )
        elif arguments.operation == "validate":
            validate_recipe(
                workspace,
                arguments.recipe,
                syntax_only=arguments.syntax_only,
            )
        elif arguments.operation == "build":
            result = build_recipe(workspace, arguments.recipe)
            print(json.dumps(result, sort_keys=True))
        else:
            manifest = verify_recipe(
                workspace,
                arguments.recipe,
                arguments.expected_key,
            )
            print(
                json.dumps(
                    {"status": "PASS", "input_key": manifest["input_key"]},
                    sort_keys=True,
                )
            )
    except (
        ImageError,
        RecipeError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"cosim-image: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

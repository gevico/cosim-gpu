#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

if [ "${GITHUB_ACTIONS:-}" != true ] ||
    [ "${RUNNER_ENVIRONMENT:-}" != github-hosted ]; then
    echo "This recipe only prepares disposable GitHub-hosted runners" >&2
    exit 1
fi
test "$(uname -m)" = x86_64
accelerator="$(python3 - "$1" <<'PY'
from pathlib import Path
import sys
from resources.images.recipe import load_recipe
print(load_recipe(Path.cwd(), sys.argv[1]).accelerator)
PY
)"
if [ "$accelerator" = kvm ]; then
    test -c /dev/kvm
    sudo chmod a+rw /dev/kvm
fi

# Remove unused toolchains from the dedicated image-build VM.
sudo rm -rf /usr/local/lib/android /usr/share/dotnet /opt/ghc \
    /usr/local/.ghcup /usr/share/swift /usr/local/share/boost
if [ "${RUNNER_TOOL_CACHE:-}" = /opt/hostedtoolcache ]; then
    sudo find "$RUNNER_TOOL_CACHE" -mindepth 1 -maxdepth 1 \
        ! -iname '*just*' -exec rm -rf -- {} +
fi
sudo apt-get clean
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    binutils openssh-client python3-venv \
    qemu-system-x86 qemu-utils xorriso curl unzip perl libdigest-sha-perl gh
df -h "$GITHUB_WORKSPACE"

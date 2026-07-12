#!/usr/bin/env bash
# Locally reproduce the openSUSE Tumbleweed distro-matrix CI job.
# Usage: bash scripts/test-opensuse-local.sh
# Requires: Docker running

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="opensuse/tumbleweed"
CONTAINER="calamus-opensuse-test"

echo "==> Pulling $IMAGE..."
docker pull "$IMAGE"

echo "==> Running openSUSE Tumbleweed test container..."
docker run --rm \
  --name "$CONTAINER" \
  -v "$REPO_ROOT":/workspace \
  -w /workspace \
  -e CC=/usr/bin/gcc \
  -e CXX=/usr/bin/g++ \
  -e AR=/usr/bin/gcc-ar \
  -e LD=/usr/bin/ld \
  -e STRIP=/usr/bin/strip \
  -e RANLIB=/usr/bin/gcc-ranlib \
  -e PKG_CONFIG=/usr/bin/pkg-config \
  "$IMAGE" \
  /bin/bash -c '
    set -euo pipefail
    export PATH="/usr/bin:/usr/sbin:/sbin:/bin:$PATH"

    echo "--- Installing system dependencies ---"
    zypper --non-interactive refresh
    zypper --non-interactive install \
      bash gcc gcc-c++ \
      python3 python3-gobject python3-cairo \
      typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 typelib-1_0-GtkSource-5 \
      libgtk-4-1 libadwaita-1-0 \
      xvfb-run dbus-1 curl git \
      cairo-devel gobject-introspection-devel python3-devel pkg-config
    ln -sf /usr/bin/gcc /usr/bin/cc && hash -r

    echo "--- Installing uv ---"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="/root/.local/bin:$PATH"

    echo "--- Installing Python 3.11 + dev dependencies ---"
    uv python install 3.11
    uv sync --extra dev

    echo "--- Running GTK integration tests ---"
    xvfb-run -a uv run pytest \
      tests/test_editor.py \
      tests/test_exporter.py \
      -v

    echo "--- Running full test suite ---"
    xvfb-run -a uv run pytest \
      --ignore=tests/test_editor.py \
      -v
  '

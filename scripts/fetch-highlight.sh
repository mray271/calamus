#!/usr/bin/env bash
# Download highlight.js for local bundling (offline code syntax highlighting in preview).
set -e

VERSION="11.9.0"
BASE="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/${VERSION}"
JS_DEST="calamus/resources/js/highlight.min.js"
CSS_DIR="calamus/resources/css"

mkdir -p "$(dirname "$JS_DEST")" "$CSS_DIR"

echo "Downloading highlight.js ${VERSION}..."
curl -fsSL "${BASE}/highlight.min.js"            -o "$JS_DEST"
curl -fsSL "${BASE}/styles/github.min.css"       -o "${CSS_DIR}/highlight-github.min.css"
curl -fsSL "${BASE}/styles/github-dark.min.css"  -o "${CSS_DIR}/highlight-github-dark.min.css"

echo "Downloaded highlight.js ${VERSION} to ${JS_DEST} and ${CSS_DIR}/"

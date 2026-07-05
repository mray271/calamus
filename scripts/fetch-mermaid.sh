#!/usr/bin/env bash
# Download mermaid.min.js 11.5.0 for local bundling
set -e
VERSION="11.5.0"
DEST="calamus/resources/js/mermaid.min.js"
mkdir -p "$(dirname "$DEST")"
curl -fsSL "https://cdn.jsdelivr.net/npm/mermaid@${VERSION}/dist/mermaid.min.js" -o "$DEST"
echo "Downloaded mermaid ${VERSION} to ${DEST}"

"""Calamus — a GTK4 Markdown editor for GNOME."""

MERMAID_VERSION = "11.5.0"
MERMAID_CDN_URL = (
    f"https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VERSION}/dist/mermaid.min.js"
)

try:
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("calamus")
    except PackageNotFoundError:
        __version__ = "0.1.0-dev"
except ImportError:
    __version__ = "0.1.0-dev"

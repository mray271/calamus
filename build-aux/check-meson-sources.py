#!/usr/bin/env python3
"""Validate that all Python modules in calamus/ are listed in meson.build.

This script checks that the install_sources() call in meson.build includes
all .py files from the calamus/ package. It helps prevent ModuleNotFoundError
at runtime when new modules are added but not registered in the build config.

Usage:
    python3 build-aux/check-meson-sources.py
    
Exit codes:
    0 - All modules are registered
    1 - Missing modules or meson.build parse error
"""

import re
import sys
from pathlib import Path


def get_python_modules(calamus_dir: Path) -> set[str]:
    """Get all .py files in calamus/ directory (non-recursive)."""
    return {f.name for f in calamus_dir.glob("*.py") if f.is_file()}


def get_registered_modules(meson_file: Path) -> set[str]:
    """Extract module names from meson.build install_sources() call."""
    try:
        with open(meson_file) as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERROR: {meson_file} not found", file=sys.stderr)
        return set()

    # Find the python.install_sources( ... ) block
    match = re.search(
        r"python\.install_sources\(\s*\[\s*(.*?)\s*\]\s*,\s*subdir:\s*'calamus'",
        content,
        re.DOTALL,
    )
    if not match:
        print(
            "ERROR: Could not find python.install_sources() in meson.build",
            file=sys.stderr,
        )
        return set()

    sources_block = match.group(1)

    # Extract all 'calamus/filename.py' entries
    modules = set()
    for match in re.finditer(r"'(calamus/([^']+\.py))'", sources_block):
        modules.add(match.group(2))

    return modules


def main() -> int:
    """Check that all Python modules are registered in meson.build."""
    repo_root = Path(__file__).parent.parent
    calamus_dir = repo_root / "calamus"
    meson_file = repo_root / "meson.build"

    # Get all .py files and registered modules
    actual_modules = get_python_modules(calamus_dir)
    registered_modules = get_registered_modules(meson_file)

    # Check for missing modules
    missing = actual_modules - registered_modules
    extra = registered_modules - actual_modules

    if missing:
        print(
            "ERROR: The following Python modules are missing from meson.build:",
            file=sys.stderr,
        )
        for module in sorted(missing):
            print(f"  - calamus/{module}", file=sys.stderr)
        print(
            "\nAdd them to the install_sources() call in meson.build, sorted alphabetically.",
            file=sys.stderr,
        )

    if extra:
        print(
            "WARNING: The following modules are registered but don't exist:",
            file=sys.stderr,
        )
        for module in sorted(extra):
            print(f"  - calamus/{module}", file=sys.stderr)

    if missing or extra:
        print(
            "\nSee CONTRIBUTING.md for more information about adding modules.",
            file=sys.stderr,
        )
        return 1

    print("✓ All Python modules are properly registered in meson.build")
    return 0


if __name__ == "__main__":
    sys.exit(main())

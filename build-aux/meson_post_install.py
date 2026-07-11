#!/usr/bin/env python3
"""Post-install script run by meson after 'meson install'.

Refreshes the GTK icon theme cache and the XDG desktop database so the
application appears in GNOME Shell / application launchers immediately.

Skipped when DESTDIR is set (e.g. during distro package builds) because the
caches must be rebuilt on the target system, not inside the staging directory.
"""

import os
import subprocess
import sys


def run(*cmd: str) -> None:
    print("+", " ".join(cmd), flush=True)
    result = subprocess.run(list(cmd))
    if result.returncode != 0:
        print(f"  warning: command exited {result.returncode}", file=sys.stderr)


def main() -> None:
    if os.environ.get("DESTDIR"):
        print("DESTDIR is set — skipping post-install cache updates.")
        return

    prefix = os.environ.get("MESON_INSTALL_PREFIX", "/usr/local")
    datadir = os.path.join(prefix, "share")

    icon_dir = os.path.join(datadir, "icons", "hicolor")
    run("gtk-update-icon-cache", "-qtf", icon_dir)

    apps_dir = os.path.join(datadir, "applications")
    run("update-desktop-database", "-q", apps_dir)


if __name__ == "__main__":
    main()

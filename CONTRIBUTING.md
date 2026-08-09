# Contributing to Calamus

Thank you for your interest in contributing!

## Code of Conduct

When interacting with this project, the [GNOME Code of Conduct](https://conduct.gnome.org/)
applies. Please read it before participating.

## Licensing

Calamus is licensed under the **GNU General Public License v3.0 or later
(GPLv3+)**. By submitting a contribution (pull request, patch, or otherwise)
you agree that your contribution is licensed under the same terms. You retain
copyright in your own contributions — no copyright assignment or Contributor
License Agreement is required.

All contributions must be compatible with GPLv3+. Modifications or
extensions to the project must preserve this license so that the software
remains free and open source. Every new source file should carry an SPDX
identifier in its header:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
```

## Questions and Support

Open a [GitHub Discussion](../../discussions) for questions, design ideas, or
help getting started. For bugs and concrete feature requests, open a
[GitHub Issue](../../issues) instead.

## SELinux Compatibility

Calamus targets Fedora as its primary platform, and **Fedora ships with SELinux
enforcing by default**. Every contributor must ensure their changes do not
introduce SELinux incompatibilities. Read [docs/selinux.md](docs/selinux.md)
before contributing.

### The subprocess allowlist

Any use of `subprocess.run()`, `subprocess.Popen()`, or `os.system()` in the
`calamus/` package **must** be pre-approved:

1. Add the command to `APPROVED_SUBPROCESS_COMMANDS` in
   `tests/test_selinux_compat.py`.
2. Document it in the Approved Subprocess Calls table in `docs/selinux.md`.
3. Add a behavioral regression test in `test_selinux_compat.py` that proves
   the call handles `PermissionError` and `OSError` gracefully (SELinux
   denials appear as these exceptions at runtime).
4. Check the SELinux item in the PR checklist.

CI will fail your PR automatically if an unapproved subprocess call is detected.

## WebKit2GTK and PyGObject API Documentation

When working with WebKit2GTK 6.0 and PyGObject bindings, **always consult the 
official PyGObject API documentation**, not older C API docs or generic WebKit 
tutorials:

- **[PyGObject WebKit-6.0 API Reference](https://api.pygobject.gnome.org/WebKit-6.0/)** — Official source of truth for Python bindings in this project
- **Key differences in WebKit2GTK 6.0**:
  - `script-message-received` signal passes `JavaScriptCore.Value` (not `WebKitJavascriptResult`)
  - Use `value.to_json(indent)` to extract JSON from messages (e.g., `value.to_json(0)`)
  - `UserMessage.get_parameters()` returns a `GLib.Variant` if used in Web Process Extensions
- **Related namespaces**:
  - [PyGObject JavaScriptCore-6.0 API Reference](https://api.pygobject.gnome.org/JavaScriptCore-6.0/) — for `JavaScriptCore.Value` methods
  - [PyGObject Gtk-4.0 API Reference](https://api.pygobject.gnome.org/Gtk-4.0/) — for GTK4 widgets

**Why this matters**: The C API documentation and old WebKit tutorials describe 
deprecated APIs. PyGObject introspection creates Python-specific bindings that 
differ significantly. Trial-and-error debugging wastes time when the official 
docs have the answers.

## Adding New Python Modules

When adding a new Python module to the `calamus/` package:

1. **Add to `meson.build`**: Register the module in the `python.install_sources()` call in `meson.build`, maintaining **alphabetical order**.
   
   ```meson
   python.install_sources(
     [
       'calamus/__init__.py',
       'calamus/new_module.py',  # ← Add here, alphabetically sorted
       ...
     ],
     subdir: 'calamus',
   )
   ```
   
   **Why**: Without this, the module will not be installed when using `meson install`, causing `ModuleNotFoundError` at runtime.

2. **Verify**: Run the validation script locally:
   ```bash
   python3 build-aux/check-meson-sources.py
   ```
   
   This will be checked automatically in CI (Build workflow).

## Code Style

All Python code must pass both [black](https://black.readthedocs.io/) and
[isort](https://pycfound.readthedocs.io/en/latest/isort/) checks. CI runs:

```
uvx black --check .
uvx isort --check-only --diff .
```

Run the same checks locally before every commit using the project's Docker
image (which has `uv` and the `dev` extras pre-installed):

```bash
docker run --rm -v "$(pwd)":/app -w /app \
    $(docker build -q .) \
    sh -c "uv sync --extra dev --no-install-project -q && uv run black . && uv run isort ."
```

Or if `uv` is available on your host:

```bash
uv sync --extra dev
uv run black .
uv run isort .
```

Formatting failures will block PR merges.

## Branch Naming

- `feature/short-description` — new features
- `bugfix/short-description` — bug fixes
- `hotfix/short-description` — urgent production fixes
- `release/version-or-milestone` — release preparation work
- `chore/short-description` — maintenance tasks
- `docs/short-description` — documentation only

## CI Pipeline

Every PR runs the following GitHub Actions workflows. All must pass before
merging (except the self-hosted SELinux enforcing job, which is advisory).

| Workflow | File | Trigger | What it checks |
|---|---|---|---|
| **Format Check** | `format.yml` | push / PR | `black --check` + `isort --check-only` |
| **Tests** | `test.yml` | push / PR | Full test suite, `--cov-fail-under=80`, JUnit + coverage artifacts |
| **Build** | `build.yml` | push / PR | `uv build` package validation |
| **Compatibility Matrix** | `compat.yml` | push / PR | Pure Python tests on 3.11/3.12/3.13; GTK tests on Fedora 44, Ubuntu 25.04, Debian 13, openSUSE Tumbleweed |
| **SELinux Audit** | `selinux.yml` | push / PR | Subprocess allowlist, graceful-failure regression, Fedora container static audit |
| **Release** | `release.yml` | `v*.*.*` tag | Builds, tests, creates GitHub Release with artifacts |

### Running the compatibility matrix locally

To replicate the distro matrix locally using Docker:

```bash
# Fedora 44
docker run --rm -v $(pwd):/app fedora:44 bash -c "
  dnf install -y python3-gobject gtk4 libadwaita gtksourceview5 \
    typelib-Gtk-4_0 typelib-Adw-1 typelib-GtkSource-5 xorg-x11-server-Xvfb curl &&
  curl -LsSf https://astral.sh/uv/install.sh | sh &&
  cd /app && /root/.local/bin/uv sync --extra dev &&
  xvfb-run -a /root/.local/bin/uv run pytest -v"

# Debian 13
docker run --rm -v $(pwd):/app debian:trixie bash -c "
  apt-get update && apt-get install -y python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 \
    gir1.2-gtksource-5 xvfb curl &&
  curl -LsSf https://astral.sh/uv/install.sh | sh &&
  cd /app && /root/.local/bin/uv sync --extra dev &&
  xvfb-run -a /root/.local/bin/uv run pytest -v"
```



```bash
git clone https://github.com/mray271/calamus.git
cd calamus
uv sync --extra dev
```

## Running Tests

```bash
uv run pytest
```

Tests require a display. Use `xvfb-run` if running headless:

```bash
xvfb-run uv run pytest
```

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat: add PDF export`
- `fix: correct undo history after reload`
- `chore: update dependencies`
- `docs: improve README install instructions`

## Pull Requests

1. Fork the repository and create a branch from `main`.
2. Add tests for any new functionality.
3. Ensure `uv run black --check .` passes.
4. Ensure `uv run pytest` passes.
5. Update `CHANGELOG.md` under `## [Unreleased]` with a brief entry.
6. Open a PR against `main`.

## Updating CHANGELOG.md

`CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com/) format.

When contributing a change:
1. Add an entry under `## [Unreleased]` in the appropriate section:
   - **Added** — new features
   - **Changed** — changes to existing functionality
   - **Deprecated** — soon-to-be removed features
   - **Removed** — removed features
   - **Fixed** — bug fixes
   - **Security** — security fixes

Example:
```markdown
## [Unreleased]

### Added
- Export to ODT format (#42)

### Fixed
- Crash when opening file with non-UTF-8 encoding (#38)
```

## Releasing (Maintainers)

1. Update `CHANGELOG.md`: move items from `[Unreleased]` to a new `[x.y.z] - YYYY-MM-DD` section.
2. Update `ReleaseNotes.md` with a human-readable summary of highlights.
3. Bump `version` in `pyproject.toml`.
4. Commit: `chore: release vX.Y.Z`
5. Tag: `git tag vX.Y.Z && git push origin vX.Y.Z`
6. The `release.yml` workflow will automatically create a GitHub Release and upload artifacts.

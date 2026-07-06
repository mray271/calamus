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

## Code Style

All Python code must be formatted with [black](https://black.readthedocs.io/):

```bash
uv run black .
```

Formatting is enforced by CI — unformatted PRs will fail.

## Branch Naming

- `feature/short-description` — new features
- `fix/short-description` — bug fixes
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
git clone https://github.com/OWNER/calamus.git
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

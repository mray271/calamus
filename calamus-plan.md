# Calamus — GTK4 Markdown Editor: Project Plan

## 1. Overview

**Calamus** is a GTK4 desktop Markdown editor targeting GNOME on Fedora, with full compatibility on Ubuntu, Linux Mint, Debian, and openSUSE. It is implemented in Python using PyGObject, licensed under **GPLv3+**, and managed with `uv` for reproducible builds.

---

## 2. License

- **GPLv3+** (GNU General Public License v3.0 or later)
- Rationale: Standard license for GNOME applications (Nautilus, GNOME Calendar, GNOME Text Editor all use GPLv3+); ensures the application and all derivative works remain open source. LGPL is appropriate for libraries, not applications.
- `LICENSE` — full GPLv3 license text

---

## 3. Technology Stack

| Concern             | Choice                          |
|---------------------|---------------------------------|
| Language            | Python 3.11+                    |
| UI Toolkit          | GTK4 via PyGObject (`gi`)       |
| Layout/Design       | Libadwaita (`Adw`) for GNOME HIG|
| Markdown Parsing    | `mistune` or `markdown-it-py`   |
| HTML→PDF Export     | `weasyprint`                    |
| HTML→ODT Export     | `odfpy` + custom converter      |
| Print Support       | GTK4 `Gtk.PrintOperation`       |
| Config Storage      | `configparser` → `~/.config/Calamus/Calamus.conf` |
| Dependency Manager  | `uv` with `uv.lock`             |
| Packaging           | `pyproject.toml` (PEP 621)      |
| Containerization    | Docker + `docker-compose.yml`   |
| Formatting          | `black`                         |
| Testing             | `pytest` + `pytest-cov`         |
| CI/CD               | GitHub Actions                  |

---

## 4. Repository Structure

```
calamus/
├── .github/
│   ├── workflows/
│   │   ├── format.yml         # black formatting compliance check
│   │   ├── test.yml           # unit + integration tests
│   │   ├── build.yml          # build and package validation
│   │   └── release.yml        # tag-triggered release + GitHub Release
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── pull_request_template.md
├── calamus/                   # main Python package
│   ├── __init__.py
│   ├── __main__.py            # entry point: python -m calamus
│   ├── app.py                 # Gtk.Application subclass
│   ├── window.py              # AdwApplicationWindow, menus, layout
│   ├── editor.py              # GtkSourceView-based Markdown editor widget
│   ├── preview.py             # WebKitGTK or TextView-based preview pane
│   ├── directorytree.py       # GtkTreeView file browser sidebar
│   ├── tabs.py                # Tab management (GtkNotebook or AdwTabView)
│   ├── formatting.py          # Markdown formatting helpers (apply to selection)
│   ├── exporter.py            # HTML, PDF, ODT export logic
│   ├── printer.py             # GTK print / print preview
│   ├── preferences.py         # Preferences dialog + config I/O
│   ├── recentfiles.py         # Track 10 most recent Markdown files
│   ├── about.py               # About dialog with version
│   └── resources/
│       ├── calamus.gresource.xml
│       ├── ui/
│       │   ├── window.ui      # GtkBuilder XML for main window
│       │   └── preferences.ui
│       └── icons/
│           └── calamus.svg
├── tests/
│   ├── __init__.py
│   ├── test_formatting.py
│   ├── test_exporter.py
│   ├── test_preferences.py
│   └── test_recentfiles.py
├── docs/
│   └── screenshots/
├── .dockerignore
├── .gitignore
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE.md
├── README.md
├── ReleaseNotes.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── uv.lock
```

---

## 5. pyproject.toml (Key Sections)

```toml
[project]
name = "calamus"
version = "0.1.0"
description = "A GTK4 Markdown editor for GNOME"
license = { text = "GPL-3.0-or-later" }
requires-python = ">=3.11"
dependencies = [
    "PyGObject>=3.46",
    "mistune>=3.0",
    "weasyprint>=61.0",
    "odfpy>=1.4",
    "markdown-it-py>=3.0",
]

[project.optional-dependencies]
dev = [
    "black",
    "pytest",
    "pytest-cov",
]

[project.scripts]
calamus = "calamus.__main__:main"

[tool.black]
line-length = 88
target-version = ["py311"]
```

---

## 6. Application Architecture

### 6.1 Main Window Layout

```
┌─────────────────────────────────────────────────────┐
│  File  Edit  Formatting  Help          [title bar]   │
├──────────┬──────────────────────────────────────────-┤
│          │  [Tab 1]  [Tab 2]  [+]                    │
│ Directory│─────────────────────────────────────────  │
│ Tree     │  Editor Pane        │  Preview Pane        │
│ (toggle) │  (GtkSourceView)   │  (WebKitGTK/HTML)    │
│          │                    │                       │
│          │                    │                       │
├──────────┴────────────────────┴───────────────────── │
│  [status bar: file path, cursor pos, word count]     │
└─────────────────────────────────────────────────────-┘
```

### 6.2 Menus

#### File Menu
| Item | Shortcut | Notes |
|------|----------|-------|
| New | Ctrl+N | New empty tab |
| Open… | Ctrl+O | GtkFileDialog, `.md` / `.markdown` filter |
| Open Recent | *(submenu)* | 10 most recent `.md` files |
| Show Directory Tree Pane | *(toggle)* | Toggleable sidebar |
| Reload | — | Reload current file from disk |
| Save | Ctrl+S | Save current tab |
| Save As… | Ctrl+Shift+S | Save with new name/path |
| --- | | |
| Next Tab | Ctrl+Page Down | |
| Previous Tab | Ctrl+Page Up | |
| Close Tab | Ctrl+W | |
| --- | | |
| Export | *(submenu)* | HTML, PDF, ODT |
| Print… | Ctrl+P | GTK PrintOperation |
| Print Preview… | Ctrl+Shift+P | |
| --- | | |
| Quit | Ctrl+Q | |

#### Edit Menu
| Item | Shortcut | Notes |
|------|----------|-------|
| Undo | Ctrl+Z | GtkSourceBuffer undo |
| Redo | Ctrl+Shift+Z | |
| --- | | |
| Cut | Ctrl+X | |
| Copy | Ctrl+C | |
| Paste | Ctrl+V | |
| --- | | |
| Go to Line… | Ctrl+G | Dialog: enter line number |
| Find… | Ctrl+F | GtkSearchBar / inline find bar |
| --- | | |
| Preferences | — | Open Preferences dialog |

#### Formatting Menu
Applies Markdown syntax to the currently selected text (or inserts at cursor).

| Item | Markdown Applied | Notes |
|------|-----------------|-------|
| **Headings** | | Submenu |
| → Heading 1 | `# ` prefix on line | |
| → Heading 2 | `## ` prefix | |
| → Heading 3 | `### ` prefix | |
| → Heading 4 | `#### ` prefix | |
| → Heading 5 | `##### ` prefix | |
| → Heading 6 | `###### ` prefix | |
| **Bold** | `**selection**` | |
| **Italic** | `*selection*` | |
| **Bold & Italic** | `***selection***` | |
| **Strikethrough** | `~~selection~~` | Widely supported extension |
| **Inline Code** | `` `selection` `` | |
| **Code Block** | ```` ```\nselection\n``` ```` | |
| **Blockquote** | `> ` prefix on each line | |
| **Ordered List** | `1. ` prefix on each line | |
| **Unordered List** | `- ` prefix on each line | |
| **Horizontal Rule** | `\n---\n` | Inserted at cursor |
| **Link** | `[selection](url)` | Prompts for URL |
| **Image** | `![alt](url)` | Prompts for URL and alt text |

#### Help Menu
| Item | Action |
|------|--------|
| What's New | Opens project GitHub Releases page (placeholder URL) |
| Get Help Online | Opens project GitHub Issues page (placeholder URL) |
| About Calamus | Shows About dialog with version number |

---

## 7. Preferences

Stored at `~/.config/Calamus/Calamus.conf` using Python `configparser`.

**Preference categories:**
- **Editor**: font family/size, tab width, spaces vs tabs, line numbers, word wrap, syntax highlighting theme, show whitespace
- **Preview**: auto-refresh on/off, refresh delay (ms), CSS theme for preview
- **Appearance**: color scheme (light/dark/system), Libadwaita style variant
- **Export**: default export directory, default PDF/HTML/ODT template
- **Files**: remember recent files (toggle), max recent files count, default open directory

---

## 8. Recent Files

- Track up to 10 most recently opened or edited `.md` files.
- Stored in `~/.config/Calamus/Calamus.conf` under `[RecentFiles]`.
- Displayed as submenu under **File → Open Recent**.
- Files that no longer exist are shown grayed out or removed automatically.

---

## 9. Docker Setup

### Dockerfile
- Base: `fedora:latest`
- Installs: `python3`, `gtk4`, `libadwaita`, `gobject-introspection`, `uv`, X11/Wayland display libs
- Runs: `uv sync` to install deps from `uv.lock`
- Sets up display forwarding environment variables

### docker-compose.yml
- Mounts `$DISPLAY` and `/tmp/.X11-unix` for GUI rendering
- Mounts project source as a volume for live development
- Provides `dev` service for running the app and `test` service for running tests

---

## 10. GitHub Actions Workflows

### `format.yml` — Formatting Compliance
- Trigger: push, pull_request to `main`
- Runs: `uv run black --check .`
- Fails PR if code is not black-formatted

### `test.yml` — Tests
- Trigger: push, pull_request to `main`
- Matrix: Python 3.11, 3.12
- Runs: `uv run pytest --cov=calamus --cov-report=xml`
- Uploads coverage to Codecov (optional)
- Uses `xvfb-run` for headless GTK tests

### `build.yml` — Build Validation
- Trigger: push to `main`, pull_request
- Runs: `uv build` to verify the package builds cleanly
- Validates `pyproject.toml` integrity

### `release.yml` — Release
- Trigger: push of tag matching `v*.*.*`
- Steps:
  1. Run tests (must pass)
  2. `uv build` → produces wheel + sdist
  3. Create GitHub Release with tag
  4. Upload artifacts to the release
  5. Optionally publish to PyPI (configurable via secret `PYPI_TOKEN`)

---

## 11. Documentation Files

### README.md
Sections:
- Project description and screenshot
- Features list
- Installation (system packages + `uv sync`)
- Running: `uv run calamus` or `python -m calamus`
- Developer setup (clone, Docker, running tests, formatting)
- Contributing link
- License

### CONTRIBUTING.md
- Code style: `black`, enforced by CI
- Branch naming: `feature/`, `fix/`, `chore/`
- PR requirements: tests must pass, black must pass
- How to run tests locally
- How to update CHANGELOG.md (Keep a Changelog format)
- Commit message convention (conventional commits recommended)

### CHANGELOG.md
- Format: [Keep a Changelog](https://keepachangelog.com) (`## [Unreleased]`, `## [x.y.z] - YYYY-MM-DD`)
- Sections per release: Added, Changed, Deprecated, Removed, Fixed, Security
- **Update process**: maintainers move items from `[Unreleased]` to a versioned section on each release; CI release workflow can validate format

### ReleaseNotes.md
- Human-readable summary of highlights per release (less technical than CHANGELOG)
- Written by maintainer at release time
- Linked from GitHub Releases

### .gitignore
- Python: `__pycache__/`, `*.pyc`, `.venv/`, `dist/`, `*.egg-info/`
- Editor: `.vscode/`, `.idea/`
- Test/coverage: `.pytest_cache/`, `htmlcov/`, `coverage.xml`
- Build: `*.gresource`

### .dockerignore
- `.git/`, `.venv/`, `__pycache__/`, `dist/`, `*.egg-info/`, `tests/`, `docs/`

---

## 12. Platform Compatibility Notes

| Distro | GTK4 Available | Notes |
|--------|---------------|-------|
| Fedora 39+ | ✅ Native | Primary target |
| Ubuntu 22.04+ | ✅ | `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1` |
| Linux Mint 21+ | ✅ | Same as Ubuntu |
| Debian 12+ | ✅ | `python3-gi`, `gir1.2-gtk-4.0` |
| openSUSE Tumbleweed | ✅ | `python3-gobject`, `typelib-1_0-Gtk-4_0` |

System GTK4 libraries must be installed via the OS package manager; only pure-Python deps go in `uv.lock`.

---

## 13. Versioning

- **Semantic Versioning**: `MAJOR.MINOR.PATCH`
- Version is the single source of truth in `pyproject.toml`
- `calamus/__init__.py` reads version at runtime: `importlib.metadata.version("calamus")`
- About dialog displays this version dynamically

---

## 14. Phase Roadmap

| Phase | Milestone | Key Deliverables |
|-------|-----------|-----------------|
| 0 | Project scaffold | Repo structure, pyproject.toml, CI, Docker, README |
| 1 | Core editor | GTK4 window, tabs, GtkSourceView editor, file open/save |
| 2 | Menus & formatting | All menus wired, Formatting menu actions |
| 3 | Preview pane | Live Markdown→HTML preview |
| 4 | Directory tree | Sidebar file browser |
| 5 | Preferences | Preferences dialog + config persistence |
| 6 | Export & Print | HTML/PDF/ODT export, GTK print |
| 7 | Recent files | Track & display recent files |
| 8 | Polish | Keyboard shortcuts, accessibility, HIG compliance |
| 9 | Release | v1.0.0, GitHub Release, packages |

---

## 15. Placeholder URLs (to update when repo is created)

- GitHub repo: `https://github.com/OWNER/calamus` *(replace OWNER)*
- What's New: `https://github.com/OWNER/calamus/releases`
- Get Help Online: `https://github.com/OWNER/calamus/issues`

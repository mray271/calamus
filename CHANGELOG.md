# Changelog

All notable changes to Calamus will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `--pipe-base-path PATH` lets piped Markdown resolve relative links from an assumed file or directory path instead of `/`

### Fixed
- Directory tree traversal now follows valid symlinked directories while safely preventing symlink cycles and pathological recursion budgets from crashing the app
- Footnote references now render as separate clickable superscripts with superscript commas, and sentence punctuation is placed before the footnote superscript run
- Resolved CodeQL findings by hardening workflow token permissions and replacing URL substring assertions with structured URL/host checks in tests

## [0.4.0] - 2026-07-12

### Added
- GLFM compatibility taxonomy in `README.md` now clearly classifies extensions as **Supported**, **Graceful fail-over**, **Not planned**, or **Available**
- GLFM table of contents token (`[[_TOC_]]`) now renders as a linked TOC built from document headings
- GLFM alerts (`> [!note]`, `> [!warning]`, etc.) now render as semantic/styled alert blockquotes
- GLFM emoji shortcodes (known Tanuki set, e.g. `:smile:`) now render as Unicode emoji
- GLFM color chips now support inline CSS functional color literals (`rgb()`, `rgba()`, `hsl()`, `hsla()`) in addition to hex literals

## [0.3.0] - 2026-07-12

### Added
- `--preview` CLI flag opens Calamus in read-only preview mode: only the preview pane is shown, the editor is non-editable, and closing the window produces no output
- Preview mode works with both file arguments (`calamus --preview file.md`) and piped input (`echo "# Hello" | calamus --preview`)
- Editing and saving actions (new, open, save, save-as, undo, redo) are disabled while in preview mode

## [0.2.0] - 2026-07-12

### Added
- Pipe mode: Ctrl+S now commits a snapshot of the current editor text as the "saved" state; the window title gains a `●` prefix when there are uncommitted edits, matching the indicator used in normal file mode
- Pipe mode: closing the window without saving now emits the original piped input unchanged (Meld-as-mergetool contract); closing after saving emits the last saved snapshot
- `Save As` action is disabled in pipe mode (no file path concept)

### Added
- Mermaid.js 11.5.0 diagram support in Preview, HTML/PDF/ODT Export, and Print
- Mermaid version displayed in Help menu and About dialog
- Initial project scaffold
- GTK4 application window with File, Edit, Formatting, and Help menus
- Tabbed Markdown editor using GtkSourceView
- Live Markdown preview pane
- Directory tree sidebar (toggleable)
- Markdown formatting menu (headings H1–H6, bold, italic, bold+italic, strikethrough, inline code, code block, blockquote, ordered list, unordered list, horizontal rule, link, image)
- Export to HTML, PDF, and ODT
- Print and Print Preview
- Find bar (Ctrl+F) and Go to Line dialog (Ctrl+G)
- Recent files tracking (10 most recent Markdown files)
- Preferences dialog with settings saved to `~/.config/Calamus/Calamus.conf`
- About dialog displaying current version
- Docker + docker-compose setup for developers (base image: fedora:44)
- GitHub Actions CI pipeline: format check (black + isort), test suite with 80% coverage gate, build validation, automated release, SELinux compatibility audit, and cross-platform compatibility matrix
- Compatibility matrix (`compat.yml`): pure Python tests across Python 3.11/3.12/3.13; GTK integration tests on Fedora 44, Ubuntu 25.04, Debian 13, and openSUSE Tumbleweed
- Three-tier SELinux compatibility enforcement: static subprocess allowlist audit, behavioral graceful-failure regression tests, and self-hosted Fedora enforcing runner support
- `docs/selinux.md` SELinux compatibility guide for developers and contributors
- GitHub Actions workflows for formatting, testing, building, and releasing

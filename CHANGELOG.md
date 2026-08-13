# Changelog

All notable changes to Calamus will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.10.0] - 2026-08-12

### Added
- **Match Diacritics** is now available in the Find dialog for both the editor and preview panes. When unchecked, searches ignore diacritic marks (e.g. `cafe` matches `café`) via Unicode folding in the editor and the preview pane's JS search engine. Closes [#97](https://github.com/mray271/calamus/issues/97).

## [0.9.4] - 2026-08-12

### Added
- **Regular Expression search in the preview pane**: the **Regular Expression** checkbox in the Find dialog is now enabled when the preview pane is the find target. Regex searches use a JavaScript `TreeWalker`-based engine injected into the WebView — matching text nodes are wrapped in `<mark>` elements with theme-aware highlight colours, and navigation wraps around. Non-regex searches continue to use WebKit's native `FindController`. JS find state is automatically invalidated on page reload so re-renders during typing do not stale-navigate. Closes [#96](https://github.com/mray271/calamus/issues/96).

## [0.9.3] - 2026-08-12

### Added
- **Find in preview pane** (Ctrl+F / Ctrl+G / Ctrl+Shift+G): when the preview pane has keyboard focus, the Find…, Find Again, and Find Again Reverse menu actions now open a search bar at the bottom of the preview and navigate matches using WebKit's `FindController` (case-insensitive, wrap-around). Closes [#93](https://github.com/mray271/calamus/issues/93).

## [0.9.2] - 2026-08-12

### Fixed
- **Copy Markdown Image** now copies to the system clipboard (both CLIPBOARD and PRIMARY selections) so middle-mouse-button paste works in other applications on Linux. Previously it only wrote to the CLIPBOARD selection. Closes [#92](https://github.com/mray271/calamus/issues/92).

## [0.9.1] - 2026-08-12

### Fixed
- **Copy Markdown Image** now appears in the right-click context menu for SVG/Mermaid `data:image/svg+xml` diagram images in the preview pane. The raw `<svg>…</svg>` text is copied to the clipboard so it can be pasted directly as an inline SVG block in Markdown. Closes [#91](https://github.com/mray271/calamus/issues/91).

## [0.9.0] - 2026-08-10

### Added
- Preview loading indicator overlay ("Rendering preview...") in WebKit 6.x with theme-aware semi-transparent background for long render operations.
- SVG context menu compatibility actions in WebKit 6.x preview:
  - **Save Image As (Compatibility SVG)...** for one-off export without changing global Mermaid preferences
  - **Copy Image (Compatibility SVG)** for one-off clipboard copy with `foreignObject` labels rewritten to text

### Fixed
- Find and Replace/Find dialogs now route Enter to the correct default action and keep Replace/Find aligned with Search Backward.
- Restored preview image right-click menu behavior in the WebKit 6.x path, including working Open Link/Open Image actions and scheme-correct URL/file routing.
- Restored preview scroll-position preservation across re-renders in the WebKit 6.x path so updates no longer snap to top.
- Added reliable image clipboard copy for preview context menu in WebKit 6.x, including Linux CLIPBOARD and PRIMARY selections.
- Restored SVG-specific image opening behavior in WebKit 6.x (`data:image/svg+xml` opens in Calamus `ImageViewerWindow`; other image types open via system viewer).
- Fixed WebKit 6.x `Save Image As...` and `Copy Image` handling for Mermaid/SVG `data:` URIs so text content is preserved through round-trip save/copy flows.
- Updated Mermaid CLI rendering config to avoid `foreignObject` labels in generated SVG output, improving compatibility with Inkscape, office suites, and non-browser image viewers.

## [0.7.0] - 2026-08-03

### Added
- Multiple instances support: Calamus now launches as an independent process each time it is invoked, relaxing GNOME's single-instance default. Users can open separate windows for different directories, mix GUI editing with piped-input workflows, and integrate Calamus freely into tool chains and macros. Closes [#76](https://github.com/mray271/calamus/issues/76).

## [0.6.3] - 2026-08-02

### Added
- `samples/why_claude_sonnet_fails_to_discover_music.md`: real-world example document featuring multiple Mermaid diagrams (graph TD, mindmap with `%%{init:%%` directive, graph LR), GFM tables with raw HTML `<img>` tags, relative subfolder image paths, and external hyperlinks
- `samples/why_claude_sonnet_fails_to_discover_music/`: companion image assets for the example document
- `tests/test_sample_music_doc.py`: integration test suite using the new sample as a fixture, covering multi-diagram rendering, `%%{init:%%` mindmap directive, `<img>` tags inside table cells, relative subfolder image path preservation, external link rendering, and full HTML export

## [0.6.1] - 2026-08-02

### Added
- Search menu and advanced search workflows:
  - Find dialog (`Ctrl+F`) with case-sensitive, regex, whole-word, and search-backward options
  - Replace/Find dialog (`Ctrl+R`) with Replace, Replace & Find, and Replace All scopes (Window / Selection / Multiple Tabs)
  - Go to Line / Column dialog (`Ctrl+L`)
  - Dialog-free search/replace accelerators (`Ctrl+G`, `Ctrl+Shift+G`, `Ctrl+T`, `Ctrl+Shift+T`, `Ctrl+H`)
  - Search history navigation with ↑/↓ in Find/Replace fields

### Fixed
- Search dialog lifecycle now preserves **Find Again/Replace Again** state while ensuring newly opened dialogs always start clean
- Preview no longer snaps to top on initial file load or when Mermaid background rendering completes
- Mermaid fenced blocks embedded inside outer markdown code fences now render as literal code examples instead of diagrams

### Changed
- `meson.build` now derives the application version directly from `pyproject.toml`, eliminating manual version-sync drift

## [0.5.5] - 2026-08-01

### Fixed
- Right-click context menu on preview images now works correctly across all image types:
  - **Open Image in New Window**: connects the WebKit `create` signal; SVG `data:` URIs (Mermaid diagrams) open in a new `ImageViewerWindow` backed by WebKit (system image viewers lack SVG support); `http/https/file://` images open in the system default app
  - **Save Image As**: replaced WebKit's broken stock download mechanism (which abandons downloads before an async file dialog can respond) with a self-contained implementation — `data:` URIs are decoded and written directly; local `file://` images are copied with `shutil`; remote `https://` images are fetched in a daemon thread with a browser-compatible User-Agent (Firefox 128 ESR, Linux x86_64)
  - **Copy Markdown Image**: replaces the unusable "Copy Image Address" (which produced a non-portable `data:` blob or absolute `file://` path); produces a ready-to-paste `![image](relative/path)` snippet, computing the path relative to the current document directory for `file://` images and using the URL verbatim for `https://` images; omitted for `data:` URI images (Mermaid diagrams have no stable file address — use a heading anchor link instead)
  - **ImageViewerWindow** (`calamus/imageviewer.py`): new lightweight SVG viewer with zoom (toolbar buttons, Ctrl++/-/0, Ctrl+scroll) and find-in-page (Ctrl+F) via `WebKit.FindController`; inlines SVG in HTML so WebKit runs in full browser mode (loading a raw `data:image/svg+xml` URI disables all browser interaction)
  - Image insert dialog (`Format → Image…`) default URL fallback changed from bare `image.png` to `https://example.com/image.png` so the inserted image renders in preview immediately

### Added
- `calamus/imageviewer.py`: lightweight WebKit-backed SVG viewer window

## [0.5.4] - 2026-08-01

### Fixed
- Images in the preview pane now scale proportionally when zooming in/out, matching the behaviour of text

## [0.5.3] - 2026-07-31

### Fixed
- Pane dividers now use a wide handle, making them significantly easier to grab and drag — especially when collapsed flush against a window edge

## [0.5.2] - 2026-07-31

### Fixed
- Passing a directory path (including `.` and `..`) on the command line no longer errors with "file not found"; the directory tree pane is instead initialised to that directory

## [0.4.5] - 2026-07-19

### Added
- Extended Markdown compatibility improvements that close several syntax support gaps

### Fixed
- Prevented symlink recursion loops in directory tree traversal
- Improved footnote superscript punctuation and placement
- Resolved CodeQL-identified issues and incorporated additional hardening updates
- Updated Mistune dependency to include upstream parser/rendering fixes

### Changed
- Release asset publishing workflow hardened for safer release delivery
- Public launch readiness documentation finalized
- Added initial Dependabot configuration scaffold

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

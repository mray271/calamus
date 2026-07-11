project(
  'calamus',
  version:       '0.1.0',
  meson_version: '>= 0.59.0',
  license:       'GPL-3.0-or-later',
)

prefix  = get_option('prefix')
bindir  = get_option('bindir')
datadir = join_paths(prefix, get_option('datadir'))

python = import('python').find_installation('python3')

# ── Python package ────────────────────────────────────────────────────────────
# Install all .py modules to <python-site-packages>/calamus/
python.install_sources(
  [
    'calamus/__init__.py',
    'calamus/__main__.py',
    'calamus/about.py',
    'calamus/app.py',
    'calamus/directorytree.py',
    'calamus/editor.py',
    'calamus/exporter.py',
    'calamus/formatting.py',
    'calamus/highlight_support.py',
    'calamus/mermaid_support.py',
    'calamus/preferences.py',
    'calamus/preview.py',
    'calamus/printer.py',
    'calamus/recentfiles.py',
    'calamus/renderer.py',
    'calamus/tabs.py',
    'calamus/theme.py',
    'calamus/window.py',
  ],
  subdir: 'calamus',
)

# Runtime resources (CSS, JS, GtkSourceView style schemes) live next to the
# .py files so that Path(__file__).parent / "resources" / ... always resolves.
install_subdir(
  'calamus/resources',
  install_dir: python.get_install_dir() / 'calamus',
)

# ── Launcher script ───────────────────────────────────────────────────────────
# configure_file replaces @PYTHON@ with the interpreter meson found, ensuring
# the installed binary uses the same Python that owns site-packages.
conf = configuration_data()
conf.set('PYTHON', python.full_path())

configure_file(
  input:         'build-aux/calamus.in',
  output:        'calamus',
  configuration: conf,
  install:       true,
  install_dir:   bindir,
  install_mode:  'rwxr-xr-x',
)

# ── Desktop entry ─────────────────────────────────────────────────────────────
install_data(
  'resources/desktop/calamus.desktop',
  install_dir: datadir / 'applications',
)

# ── Application icons ─────────────────────────────────────────────────────────
install_data(
  'resources/desktop/calamus.svg',
  install_dir: datadir / 'icons' / 'hicolor' / 'scalable' / 'apps',
)
install_data(
  'resources/desktop/calamus_48x48.png',
  install_dir: datadir / 'icons' / 'hicolor' / '48x48' / 'apps',
  rename: 'calamus.png',
)
install_data(
  'resources/desktop/calamus_128x128.png',
  install_dir: datadir / 'icons' / 'hicolor' / '128x128' / 'apps',
  rename: 'calamus.png',
)
install_data(
  'resources/desktop/calamus_256x256.png',
  install_dir: datadir / 'icons' / 'hicolor' / '256x256' / 'apps',
  rename: 'calamus.png',
)

# ── Post-install: refresh desktop and icon caches ────────────────────────────
meson.add_install_script(python.full_path(), files('build-aux/meson_post_install.py'))

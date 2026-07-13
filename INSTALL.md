# Installing Calamus

This guide covers two installation paths:

| Path | Best for | Tool |
|------|----------|------|
| [System install](#system-install-meson) | End users — `git clone` and launch from the app grid | `meson` + `make` |
| [Developer install](#developer-install-uv) | Hacking on the code, running tests | `uv` |

---

## System install (meson)

A system install places the Python package into site-packages, generates a
`calamus` binary on your `PATH`, and registers the desktop entry and icons so
the app appears in GNOME Shell / your application launcher.

### 1. Install system dependencies

GTK4 and PyGObject must come from your distro — do **not** install them via
pip.  Install the build tools (`meson`, `ninja-build`) the same way.

**Fedora 44+**
```bash
sudo dnf install \
    python3-gobject gtk4 libadwaita gtksourceview5 \
    python3-mistune python3-weasyprint python3-odfpy \
    google-noto-color-emoji-fonts \
    meson ninja-build
```

> **SELinux note (Fedora):** On first run after install, if the app fails to
> start, test in permissive mode (`sudo setenforce 0`) to surface any AVC
> denials, then re-enable (`sudo setenforce 1`). See
> [docs/selinux.md](docs/selinux.md) for the full guide.

**Ubuntu 25.04+ / Linux Mint 22.x+**
```bash
sudo apt install \
    python3-gi python3-gi-cairo gir1.2-gtk-4.0 \
    gir1.2-adw-1 gir1.2-gtksource-5 libgtk-4-1 libadwaita-1-0 \
    python3-mistune python3-weasyprint python3-odfpy \
    meson ninja-build
```

**Debian 13+**
```bash
sudo apt install \
    python3-gi python3-gi-cairo gir1.2-gtk-4.0 \
    gir1.2-adw-1 gir1.2-gtksource-5 libgtk-4-1 libadwaita-1-0 \
    python3-mistune python3-weasyprint python3-odfpy \
    meson ninja-build
```

**openSUSE Tumbleweed**
```bash
sudo zypper install \
    python3-gobject typelib-1_0-Gtk-4_0 \
    typelib-1_0-Adw-1 typelib-1_0-GtkSource-5 \
    python3-mistune python3-weasyprint python3-odfpy \
    meson ninja-build
```

### 2. Clone the repository

```bash
git clone https://github.com/mray271/calamus.git
cd calamus
```

### 3. Fetch Mermaid.js (optional — required for diagram support)

```bash
bash scripts/fetch-mermaid.sh
```

This downloads `mermaid.min.js` into `calamus/resources/js/` for offline
diagram rendering. The app runs without it but ` ```mermaid ` blocks will fall
back to CDN or render as plain text.

### 4. Build and install

**System-wide** (installs to `/usr`, requires `sudo` for the install step):
```bash
make
sudo make install
```

**Per-user** (installs to `~/.local`, no `sudo` required):
```bash
make PREFIX=~/.local
make install PREFIX=~/.local
```

> **Per-user PATH note:** Ensure `~/.local/bin` is on your `PATH`.  On most
> distros this is set automatically, but you can verify with `echo $PATH` and
> add `export PATH="$HOME/.local/bin:$PATH"` to your shell profile if needed.

The install step:
- copies all Python modules to site-packages (`calamus/`)
- installs runtime resources (CSS, JS, style schemes) alongside the modules
- writes a `calamus` launcher binary to `bin/`
- registers the `.desktop` entry and all icon sizes under `share/`
- runs `gtk-update-icon-cache` and `update-desktop-database`

After install, launch Calamus from the application grid or run:
```bash
calamus
```

### 5. Uninstall

```bash
sudo make uninstall          # matches whatever PREFIX was used at install time
# or for per-user:
make uninstall PREFIX=~/.local
```

### Switching prefix / reconfiguring

If you want to change the install prefix after an initial `make`:
```bash
make reconfigure PREFIX=/usr/local
sudo make install
```

---

## Developer install (uv)

Use this path when you want to work on the source code, run tests, or try the
app before committing to a system install.

### 1. Install system dependencies

Same GTK4 / PyGObject packages as above — pick the block for your distro.
You do **not** need `meson` or `ninja-build` for the developer install.

### 2. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Clone and set up the virtualenv

```bash
git clone https://github.com/mray271/calamus.git
cd calamus
uv sync --extra dev
```

### 4. Fetch Mermaid.js (optional)

```bash
bash scripts/fetch-mermaid.sh
```

### 5. Run

```bash
uv run calamus
# or
python -m calamus
```

---

## Packaging

| Format | Guide |
|--------|-------|
| **RPM** (Fedora) | [resources/rpm/calamus.spec](resources/rpm/calamus.spec) — uses `%pyproject_*` macros |
| **Flatpak** | [resources/flatpak/io.github.mray271.calamus.yaml](resources/flatpak/io.github.mray271.calamus.yaml) — targets GNOME 48 runtime |

See the [Packaging & Distribution](README.md#packaging--distribution) section
of `README.md` for step-by-step build instructions for each format.

---

## Troubleshooting

**`calamus: command not found` after system install**  
The `calamus` binary is at `/usr/bin/calamus` (or `~/.local/bin/calamus` for
per-user). Run `which calamus` to confirm it is on your PATH.

**App won't start — `ImportError: No module named 'gi'`**  
The PyGObject bindings are missing. Install `python3-gobject` (Fedora) or
`python3-gi` (Debian/Ubuntu) from your distro packages. Do not install
`PyGObject` via pip for a system install.

**App won't start — `ImportError: No module named 'mistune'`** (or weasyprint / odfpy)  
Install the missing dependency via your distro package manager (see step 1
above). As a temporary fallback: `pip3 install --break-system-packages mistune`.

**Diagrams not rendering**  
Run `bash scripts/fetch-mermaid.sh` to download the bundled Mermaid.js. The
app renders diagrams client-side in the WebKit preview without network access
once this file is present.

**SELinux denial on Fedora**  
See [docs/selinux.md](docs/selinux.md).

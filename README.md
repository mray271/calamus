# Calamus

A GTK4 Markdown editor for GNOME — clean, fast, and compatible with Fedora, Ubuntu, Linux Mint, Debian, and openSUSE.

## Features

- Tabbed Markdown editing with live preview
- Full Markdown formatting toolbar (headings, bold, italic, lists, links, code, and more)
- Directory tree sidebar for navigating project files
- Export to HTML, PDF, and ODT
- Print and Print Preview via GTK
- Recent files (last 10 opened Markdown files)
- Find, Go to Line, Undo/Redo
- Preferences stored in `~/.config/Calamus/Calamus.conf`
- Dark/light/system theme support via Libadwaita

## Platform Compatibility

| Distribution | Minimum Version | GTK4 Version |
|---|---|---|
| Fedora | 44 | 4.22.x+ |
| Ubuntu | 25.04 | 4.22.x |
| Linux Mint | 22.x | 4.22.x |
| Debian | 13 (Trixie) | 4.22.x |
| openSUSE | Tumbleweed (rolling) | 4.22.x |

> **Note:** Older LTS releases (Ubuntu 24.04, Debian 12) ship GTK 4.14 and are **not** supported.

## Requirements

Calamus requires **GTK >= 4.22.4** (current stable as of April 2026).

### System packages

**Fedora 44+:**
```bash
sudo dnf install python3-gobject gtk4 libadwaita gtksourceview5 \
    typelib-Gtk-4_0 typelib-Adw-1 typelib-GtkSource-5
```

> **SELinux note (Fedora):** Fedora runs SELinux enforcing by default. On first
> run, test in permissive mode (`sudo setenforce 0`) to surface any denials, then
> re-enable (`sudo setenforce 1`). See [docs/selinux.md](docs/selinux.md) for
> the full guide.

**Ubuntu 25.04+ / Linux Mint 22.x+:**
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 \
    gir1.2-adw-1 gir1.2-gtksource-5 libgtk-4-1 libadwaita-1-0
```

**Debian 13+:**
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 \
    gir1.2-adw-1 gir1.2-gtksource-5 libgtk-4-1 libadwaita-1-0
```

**openSUSE Tumbleweed:**
```bash
sudo zypper install python3-gobject typelib-1_0-Gtk-4_0 \
    typelib-1_0-Adw-1 typelib-1_0-GtkSource-5
```

### uv (Python dependency manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Installation

```bash
git clone https://github.com/OWNER/calamus.git
cd calamus
uv sync --extra dev
```

### Download Mermaid.js (required for diagram support)

```bash
bash scripts/fetch-mermaid.sh
```

This downloads `mermaid.min.js` 11.5.0 into `calamus/resources/js/` for offline diagram rendering.

## Running

```bash
uv run calamus
# or
python -m calamus
```

## Development

### Setup

```bash
uv sync --extra dev
```

### Running tests

```bash
uv run pytest
```

### Checking formatting

```bash
uv run black --check .
```

### Auto-formatting

```bash
uv run black .
```

### Using Docker

Docker provides a fully self-contained development environment with all system GTK4
dependencies pre-installed. No local GTK libraries required.

**Build the image:**

```bash
docker compose build
```

**Run the application** (requires a running X11 or Wayland display):

```bash
# Grant local Docker containers access to your X server
xhost +local:docker

docker compose up app
```

> **Fedora / SELinux note:** The `docker-compose.yml` passes
> `--security-opt label=type:container_runtime_t` so the container can reach
> the X11 socket without needing `--privileged`. The three pieces that work
> together are:
> - `xhost +local:docker` — lets local Docker containers connect to your X server
> - `DISPLAY=$DISPLAY` — tells GTK which display to use
> - `/tmp/.X11-unix` mount — exposes the Unix socket the app communicates over

**Run the full test suite:**

```bash
docker compose run --rm test
```

**Run a single test file:**

```bash
docker compose run --rm test uv run pytest tests/test_mermaid_support.py -v
```

**Check code formatting:**

```bash
docker compose run --rm format-check
```

**Auto-format code:**

```bash
docker compose run --rm format-check uv run black .
```

**Open an interactive shell in the container:**

```bash
docker compose run --rm app bash
```

**Rebuild after dependency changes:**

```bash
docker compose build --no-cache
```

#### Troubleshooting: `Invalid MIT-MAGIC-COOKIE-1 key`

If the app still complains about X authorization after running `xhost +local:docker`,
mount your `.Xauthority` file into the container. Uncomment the `XAUTHORITY` lines
in `docker-compose.yml`, or add the flag manually:

```bash
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  --volume="$HOME/.Xauthority:/root/.Xauthority:ro" \
  --security-opt label=type:container_runtime_t \
  <image_name> uv run calamus
```

> If your container runs as a non-root user, replace `/root/.Xauthority` with
> that user's home directory, e.g. `/home/myuser/.Xauthority`.

## Project Structure

```
calamus/           Main Python package
tests/             Test suite (pytest)
.github/workflows/ CI/CD pipelines
docs/              Documentation and screenshots
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

GNU Lesser General Public License v2.1 or later. See [LICENSE](LICENSE).

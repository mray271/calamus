# Install prefix. Override with: make install PREFIX=/usr/local
PREFIX   ?= /usr
# Meson build directory
BUILDDIR ?= builddir

# ── System install (meson + ninja) ───────────────────────────────────────────
#
# Typical end-user workflow:
#   make              # configure + compile (meson setup + meson compile)
#   sudo make install # install to $(PREFIX)
#   sudo make uninstall
#
# Dependencies required on the host before installing:
#   Fedora:  sudo dnf install python3-gobject gtk4 libadwaita gtksourceview5 \
#                             python3-mistune python3-weasyprint python3-odfpy \
#                             meson ninja-build
#   Ubuntu:  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 \
#                             gir1.2-adw-1 gir1.2-gtksource-5 \
#                             python3-mistune python3-weasyprint python3-odfpy \
#                             meson ninja-build

all: $(BUILDDIR)/build.ninja
	meson compile -C $(BUILDDIR)

$(BUILDDIR)/build.ninja:
	meson setup $(BUILDDIR) --prefix=$(PREFIX)

install: $(BUILDDIR)/build.ninja
	meson install -C $(BUILDDIR)

uninstall: $(BUILDDIR)/build.ninja
	sudo ninja -C $(BUILDDIR) uninstall

clean:
	rm -rf $(BUILDDIR)

# Reconfigure (e.g. after changing meson.build or switching PREFIX):
#   make reconfigure PREFIX=/usr/local
reconfigure:
	meson setup --reconfigure $(BUILDDIR) --prefix=$(PREFIX)

# ── Docker developer workflow ─────────────────────────────────────────────────

up:
	docker compose up

up-detach:
	docker compose up -d

down:
	docker compose down

# ── Formatting ────────────────────────────────────────────────────────────────

format:
	docker compose run --rm test sh -c "uv run black . && uvx isort ."

format-check:
	docker compose run --rm test sh -c "uv run black --check . && uvx isort --check-only --diff ."

.PHONY: all install uninstall clean reconfigure up up-detach down format format-check

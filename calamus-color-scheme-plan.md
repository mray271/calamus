# Plan: Dark/Light Theme Toggle + gsettings Signal Support

## Context & Current State

- `app.py` has an experimental `on_color_scheme_changed` that connects to
  `Gio.Settings("org.gnome.desktop.interface")` `changed::color-scheme` but it
  is partially wired and hard-codes `PREFER_DARK` on every launch.
- `preferences.py` already persists `Appearance.color_scheme` = `"system"` |
  `"light"` | `"dark"` via `FileConfigProvider`, but the value is never read
  back and applied to `Adw.StyleManager` at startup.
- The hamburger menu (`MENU_XML`) has no color-scheme item.
- **Docker dbus problem**: `docker-entrypoint.sh` does not start a D-Bus session
  daemon. `Gio.Settings` for `org.gnome.desktop.interface` requires a running
  D-Bus session; without one the `Gio.Settings.new()` call raises a GLib
  warning and the signal is never delivered. `gnome-extensions-app` (which
  installs `gsettings`) is already in the Dockerfile, so we can actuate the
  setting inside the container once dbus is running.

---

## Part 1 — Fix D-Bus in Docker

**File:** `docker-entrypoint.sh`

Start a D-Bus session daemon before launching the app. Export
`DBUS_SESSION_BUS_ADDRESS` so every child process inherits it.

```sh
# After the mkdir -p block, before `exec "$@"`:
if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
    eval "$(dbus-launch --sh-syntax --exit-with-session)"
    export DBUS_SESSION_BUS_ADDRESS
fi
exec "$@"
```

**Why `--exit-with-session`**: the daemon exits when the entrypoint process
exits, so no zombie dbus-daemon is left behind.

**Verify inside container** (developer workflow):
```sh
gsettings set org.gnome.desktop.interface color-scheme prefer-dark
gsettings get org.gnome.desktop.interface color-scheme   # → 'prefer-dark'
```

No changes needed to `docker-compose.yml` for this — the env var is already
forwarded (`DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-}`). Inside the
container, the entrypoint will set it when it is empty.

---

## Part 2 — ThemeManager (new module: `calamus/theme.py`)

Centralise all color-scheme logic so `app.py` and `window.py` stay thin.

### Responsibilities
1. Read the saved `Appearance.color_scheme` from config at startup.
2. Apply the scheme to `Adw.StyleManager`.
3. Subscribe to `Gio.Settings("org.gnome.desktop.interface")`
   `changed::color-scheme` with a safe fallback when D-Bus is unavailable
   (catches `GLib.Error` and logs a warning instead of crashing).
4. When a gsettings signal arrives **and** the user's saved preference is
   `"system"`, propagate the change through `Adw.StyleManager` and persist
   `"system"` back (no-op if already stored).
5. Expose a `set_scheme(scheme: str)` method (`"system"` | `"light"` | `"dark"`)
   that updates the `StyleManager`, saves to config, and keeps the
   `Gio.SimpleAction` state in sync.
6. Expose a `get_scheme() -> str` method for reading current state.

### Adw.ColorScheme mapping
| Config value | `Adw.ColorScheme`           |
|--------------|-----------------------------|
| `"system"`   | `DEFAULT` (follows gsettings)|
| `"light"`    | `FORCE_LIGHT`               |
| `"dark"`     | `FORCE_DARK`                |

### Safe gsettings subscription
```python
def _try_connect_gsettings(self) -> None:
    try:
        settings = Gio.Settings.new("org.gnome.desktop.interface")
        settings.connect("changed::color-scheme", self._on_gsettings_changed)
        self._gsettings = settings   # keep a reference so it isn't GC'd
    except GLib.Error as exc:
        import warnings
        warnings.warn(f"gsettings unavailable (D-Bus not running?): {exc}")
```

This ensures the app starts cleanly on hosts where `org.gnome.desktop.interface`
schema is not installed (non-GNOME desktops, minimal CI containers, etc.).

---

## Part 3 — Hamburger Menu Item

**File:** `calamus/window.py` — `MENU_XML`

Add a **View** submenu (or insert into existing structure) with a
**Color Scheme** section containing three radio-style items wired to a
stateful string action `app.color-scheme`:

```xml
<submenu>
  <attribute name="label">View</attribute>
  <section>
    <attribute name="label">Color Scheme</attribute>
    <item>
      <attribute name="label">Follow System</attribute>
      <attribute name="action">app.color-scheme</attribute>
      <attribute name="target">system</attribute>
    </item>
    <item>
      <attribute name="label">Light</attribute>
      <attribute name="action">app.color-scheme</attribute>
      <attribute name="target">light</attribute>
    </item>
    <item>
      <attribute name="label">Dark</attribute>
      <attribute name="action">app.color-scheme</attribute>
      <attribute name="target">dark</attribute>
    </item>
  </section>
</submenu>
```

GTK4 renders string-target items as radio buttons; the checked item tracks
the action's current state automatically.

---

## Part 4 — Stateful Action in `window.py`

Register a `GLib.VariantType("s")` stateful action in `_build_actions()`:

```python
initial_scheme = theme_manager.get_scheme()   # "system"|"light"|"dark"
scheme_action = Gio.SimpleAction.new_stateful(
    "color-scheme",
    GLib.VariantType.new("s"),
    GLib.Variant.new_string(initial_scheme),
)
scheme_action.connect("activate", self._on_color_scheme_action)
app.add_action(scheme_action)
self._scheme_action = scheme_action
```

Handler:
```python
def _on_color_scheme_action(
    self, action: Gio.SimpleAction, param: GLib.Variant
) -> None:
    scheme = param.get_string()           # "system"|"light"|"dark"
    action.set_state(GLib.Variant.new_string(scheme))
    theme_manager.set_scheme(scheme)
```

---

## Part 5 — Wire ThemeManager into `app.py`

Replace the ad-hoc code in `do_activate` with `ThemeManager`:

```python
from calamus.theme import ThemeManager

def do_activate(self) -> None:
    self._theme_manager = ThemeManager()   # reads config, applies scheme, hooks gsettings
    window = self.get_active_window()
    if window is None:
        window = CalamusWindow(application=self, theme_manager=self._theme_manager)
    window.present()
```

`CalamusWindow.__init__` accepts `theme_manager` so it can pass it to
`_build_actions()` for the stateful action's initial state and callback target.

---

## Part 6 — Keep Preferences Dialog In Sync

`PreferencesDialog` already has a `theme_row` ComboRow. Currently it saves to
config but the saved value is never re-applied. After this change:

- On `PreferencesDialog` open, set `theme_row.set_selected()` from
  `theme_manager.get_scheme()` (live state, not re-reading config).
- On save (`_on_close`), call `theme_manager.set_scheme(scheme)` instead of
  writing directly to config — `ThemeManager.set_scheme` handles both the
  `StyleManager` update and the config write.

This means the Preferences dialog and the hamburger menu item stay in sync
through the shared `ThemeManager` instance.

---

## Part 7 — gsettings → App State Sync (runtime)

When `ThemeManager._on_gsettings_changed` fires:

```python
def _on_gsettings_changed(self, settings: Gio.Settings, key: str) -> None:
    if self._scheme != "system":
        return   # user has an explicit override — gsettings changes are ignored
    # Adw.StyleManager already follows gsettings when scheme == DEFAULT.
    # Notify any listeners (e.g., preview WebView CSS) that dark mode changed.
    self._notify_dark_changed()
```

Since `Adw.ColorScheme.DEFAULT` tells libadwaita to follow the system setting
automatically, there is no manual `StyleManager` call needed here — libadwaita
handles it. The only work is notifying downstream consumers (e.g., the Mermaid
preview WebView needs to switch its CSS theme).

---

## Part 8 — Preview CSS Theming (downstream consumer)

`calamus/preview.py` / `calamus/renderer.py` — ensure the HTML preview
respects `Adw.StyleManager.get_dark()`:

- Pass a `dark: bool` flag into the renderer when generating HTML, toggling
  between a light and dark CSS stylesheet (or adding `class="dark"` to
  `<body>`).
- Connect `Adw.StyleManager.get_default().connect("notify::dark", ...)` in the
  preview widget to trigger a re-render when the system or user changes the
  scheme.

---

## File Change Summary

| File | Change |
|------|--------|
| `docker-entrypoint.sh` | Start `dbus-launch` when `DBUS_SESSION_BUS_ADDRESS` is empty |
| `calamus/theme.py` | **New file** — `ThemeManager` class |
| `calamus/app.py` | Replace ad-hoc color scheme code with `ThemeManager` |
| `calamus/window.py` | Add `color-scheme` stateful action; add View/Color Scheme submenu in `MENU_XML`; accept `theme_manager` param |
| `calamus/preferences.py` | Route save/load through `ThemeManager` instead of raw config |
| `calamus/preview.py` | Connect `notify::dark` to trigger re-render |

---

## Developer Testing Workflow (Docker)

```sh
make up                        # starts container with dbus via entrypoint
# Inside container or via `docker compose exec app bash`:
gsettings set org.gnome.desktop.interface color-scheme prefer-dark
# → app switches to dark mode in real time (if scheme == "system")
gsettings set org.gnome.desktop.interface color-scheme default
# → app switches back to light mode

# Test in-app override:
# Click hamburger → Color Scheme → Dark  (ignores gsettings from here)
# Click hamburger → Color Scheme → Follow System  (resumes gsettings)
```

---

## Non-Goals / Out of Scope

- Writing actual gsettings values back from Calamus (Calamus sets its own local
  override; it never mutates system-wide gsettings).
- Wayland `org.freedesktop.portal.Settings` support (future work once the app
  runs under Wayland).

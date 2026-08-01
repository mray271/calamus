"""Lightweight WebKit-backed image viewer window.

Used when the system default image viewer does not support the image format
(e.g. gthumb and eog lack full SVG support).  WebKit, already a Calamus
dependency, renders SVG perfectly.
"""

from __future__ import annotations

import base64
from urllib.parse import unquote

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GLib, Gtk

try:
    gi.require_version("WebKit", "6.0")
    from gi.repository import WebKit as _WebKitModule

    _WEBKIT_AVAILABLE = True
except (ImportError, ValueError):
    _WebKitModule = None
    _WEBKIT_AVAILABLE = False

_VIEWER_HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{
    margin: 0;
    padding: 1em;
    background: #f5f5f5;
    box-sizing: border-box;
  }}
  svg {{
    max-width: 100%;
    height: auto;
    display: block;
  }}
</style>
</head>
<body>
{svg}
</body>
</html>
"""

_ZOOM_STEP = 1.15
_ZOOM_MIN = 0.25
_ZOOM_MAX = 5.0
_ZOOM_DEFAULT = 1.0


def _svg_html(data_uri: str) -> str:
    """Decode an SVG data: URI and wrap it in a full HTML document.

    Loading a raw ``data:image/svg+xml`` URI puts WebKit into image-document
    mode, which disables all browser features.  Inlining the SVG inside an
    HTML page restores full browser behaviour.
    """
    header, _, data_part = data_uri.partition(",")
    if ";base64" in header:
        svg_text = base64.b64decode(data_part).decode("utf-8", errors="replace")
    else:
        svg_text = unquote(data_part)
    return _VIEWER_HTML.format(svg=svg_text)


class ImageViewerWindow(Adw.Window):
    """A read-only SVG viewer backed by a WebKitWebView.

    Features:
      - Scroll / pan via scrollbar
      - Zoom in/out/reset: toolbar buttons, Ctrl++/-, Ctrl+0, Ctrl+scroll
      - Text selection and Copy on SVG text elements
      - Find in page: Ctrl+F opens a search bar (Enter = next, Shift+Enter = prev)
    """

    def __init__(self, uri: str, title: str = "Image Viewer", **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title(f"Calamus \u2014 {title}")
        self.set_default_size(900, 700)

        app = Gtk.Application.get_default()
        if app is not None:
            self.set_application(app)

        self._zoom = _ZOOM_DEFAULT
        self._view: object = None
        self._find_controller: object = None

        self._build_ui(uri)
        self._build_key_controller()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self, uri: str) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(box)

        # Header bar with zoom controls
        header = Adw.HeaderBar()
        box.append(header)

        for icon, tooltip, callback in [
            ("zoom-in-symbolic",      "Zoom in (Ctrl++)",     self._on_zoom_in),
            ("zoom-out-symbolic",     "Zoom out (Ctrl+-)",    self._on_zoom_out),
            ("zoom-fit-best-symbolic","Reset zoom (Ctrl+0)",  self._on_zoom_reset),
        ]:
            btn = Gtk.Button(icon_name=icon)
            btn.set_tooltip_text(tooltip)
            btn.connect("clicked", callback)
            header.pack_end(btn)

        find_btn = Gtk.ToggleButton(icon_name="edit-find-symbolic")
        find_btn.set_tooltip_text("Find in page (Ctrl+F)")
        header.pack_end(find_btn)
        self._find_btn = find_btn

        if not _WEBKIT_AVAILABLE:
            label = Gtk.Label(
                label="WebKit is not available \u2014 cannot display image."
            )
            label.set_hexpand(True)
            label.set_vexpand(True)
            box.append(label)
            return

        context = _WebKitModule.WebContext.get_default()
        if hasattr(context, "set_sandbox_enabled"):
            context.set_sandbox_enabled(False)

        view = _WebKitModule.WebView()
        view.set_hexpand(True)
        view.set_vexpand(True)
        self._view = view

        # Load SVG inlined in HTML so WebKit runs in full browser mode.
        html = _svg_html(uri)
        raw = GLib.Bytes.new(html.encode("utf-8"))
        view.load_bytes(raw, "text/html", "utf-8", "file:///")

        # Ctrl+scroll → zoom
        scroll_ctrl = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll_ctrl.connect("scroll", self._on_scroll)
        view.add_controller(scroll_ctrl)

        box.append(view)

        # Find bar (hidden until Ctrl+F / toggle button)
        self._find_controller = view.get_find_controller()
        find_bar = self._build_find_bar()
        box.append(find_bar)
        self._find_bar = find_bar

        find_btn.connect("toggled", self._on_find_toggled)

    def _build_find_bar(self) -> Gtk.SearchBar:
        bar = Gtk.SearchBar()
        bar.set_show_close_button(True)

        entry = Gtk.SearchEntry()
        entry.set_placeholder_text("Find in page…")
        entry.set_hexpand(True)
        bar.set_child(entry)
        bar.connect_entry(entry)
        self._find_entry = entry

        entry.connect("search-changed", self._on_find_changed)
        entry.connect("activate", self._on_find_next)
        entry.connect("next-match", self._on_find_next)
        entry.connect("previous-match", self._on_find_prev)
        bar.connect("notify::search-mode-enabled",
                    lambda b, _: self._sync_find_btn())
        return bar

    def _build_key_controller(self) -> None:
        ctrl = Gtk.EventControllerKey.new()
        ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(ctrl)

    # ── Zoom ─────────────────────────────────────────────────────────────────

    def _set_zoom(self, level: float) -> None:
        self._zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, level))
        if self._view is not None:
            self._view.set_zoom_level(self._zoom)

    def _on_zoom_in(self, *_) -> None:
        self._set_zoom(self._zoom * _ZOOM_STEP)

    def _on_zoom_out(self, *_) -> None:
        self._set_zoom(self._zoom / _ZOOM_STEP)

    def _on_zoom_reset(self, *_) -> None:
        self._set_zoom(_ZOOM_DEFAULT)

    def _on_scroll(
        self,
        controller: Gtk.EventControllerScroll,
        _dx: float,
        dy: float,
    ) -> bool:
        mods = controller.get_current_event_state()
        if mods & Gdk.ModifierType.CONTROL_MASK:
            if dy < 0:
                self._on_zoom_in()
            else:
                self._on_zoom_out()
            return True  # consumed
        return False

    # ── Find ─────────────────────────────────────────────────────────────────

    def _open_find(self) -> None:
        self._find_bar.set_search_mode(True)
        self._find_entry.grab_focus()

    def _close_find(self) -> None:
        self._find_bar.set_search_mode(False)
        if self._find_controller is not None:
            self._find_controller.search_finish()

    def _on_find_toggled(self, btn: Gtk.ToggleButton) -> None:
        if btn.get_active():
            self._open_find()
        else:
            self._close_find()

    def _sync_find_btn(self) -> None:
        active = self._find_bar.get_search_mode()
        self._find_btn.set_active(active)

    def _on_find_changed(self, entry: Gtk.SearchEntry) -> None:
        if self._find_controller is None:
            return
        text = entry.get_text()
        if text:
            self._find_controller.search(
                text,
                _WebKitModule.FindOptions.WRAP_AROUND
                | _WebKitModule.FindOptions.CASE_INSENSITIVE,
                500,
            )
        else:
            self._find_controller.search_finish()

    def _on_find_next(self, *_) -> None:
        if self._find_controller is not None:
            self._find_controller.search_next()

    def _on_find_prev(self, *_) -> None:
        if self._find_controller is not None:
            self._find_controller.search_previous()

    # ── Keyboard ─────────────────────────────────────────────────────────────

    def _on_key_pressed(
        self,
        _ctrl: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)

        if ctrl:
            if keyval in (Gdk.KEY_equal, Gdk.KEY_plus, Gdk.KEY_KP_Add):
                self._on_zoom_in()
                return True
            if keyval in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract):
                self._on_zoom_out()
                return True
            if keyval in (Gdk.KEY_0, Gdk.KEY_KP_0):
                self._on_zoom_reset()
                return True
            if keyval == Gdk.KEY_f and not shift:
                self._open_find()
                return True

        if keyval == Gdk.KEY_Escape and self._find_bar.get_search_mode():
            self._close_find()
            return True

        return False

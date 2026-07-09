"""Theme management — applies and persists the app color scheme."""

from __future__ import annotations

import warnings

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gio

from calamus.preferences import AbstractConfigProvider, FileConfigProvider

_SCHEME_TO_ADW: dict[str, Adw.ColorScheme] = {
    "system": Adw.ColorScheme.DEFAULT,
    "light": Adw.ColorScheme.FORCE_LIGHT,
    "dark": Adw.ColorScheme.FORCE_DARK,
}


class ThemeManager:
    """Manages the application color scheme.

    * Reads ``Appearance.color_scheme`` from config at startup and applies it to
      ``Adw.StyleManager``.
    * Subscribes to ``org.gnome.desktop.interface changed::color-scheme`` via
      ``Gio.Settings`` so that system-wide GNOME dark-style changes are picked
      up when the user's preference is ``"system"``.  The subscription is
      wrapped in a try/except so the app starts cleanly when D-Bus is
      unavailable (non-GNOME desktops, minimal containers).
    * Exposes :meth:`set_scheme` / :meth:`get_scheme` for in-app overrides.
    """

    def __init__(
        self,
        config_provider: AbstractConfigProvider | None = None,
        style_manager: Adw.StyleManager | None = None,
    ) -> None:
        self._config_provider = config_provider or FileConfigProvider()
        self._gsettings: Gio.Settings | None = None
        self._style_manager = style_manager or Adw.StyleManager.get_default()

        config = self._config_provider.load()
        self._scheme: str = config.get("Appearance", "color_scheme", fallback="system")
        if self._scheme not in _SCHEME_TO_ADW:
            self._scheme = "system"

        self._apply_adw_scheme(self._scheme)
        self._try_connect_gsettings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_scheme(self) -> str:
        """Return current saved scheme: ``'system'``, ``'light'``, or ``'dark'``."""
        return self._scheme

    def get_dark(self) -> bool:
        """Return ``True`` if the app is currently rendered in dark mode."""
        return self._style_manager.get_dark()

    def set_scheme(self, scheme: str) -> None:
        """Set the color scheme, apply it to ``Adw.StyleManager``, and persist.

        Args:
            scheme: One of ``'system'``, ``'light'``, or ``'dark'``.
        """
        if scheme not in _SCHEME_TO_ADW:
            raise ValueError(
                f"Invalid scheme {scheme!r}; expected 'system', 'light', or 'dark'"
            )
        self._scheme = scheme
        self._apply_adw_scheme(scheme)
        self._persist_scheme(scheme)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_adw_scheme(self, scheme: str) -> None:
        self._style_manager.set_color_scheme(_SCHEME_TO_ADW[scheme])

    def _persist_scheme(self, scheme: str) -> None:
        config = self._config_provider.load()
        config["Appearance"]["color_scheme"] = scheme
        self._config_provider.save(config)

    def _try_connect_gsettings(self) -> None:
        """Subscribe to org.gnome.desktop.interface color-scheme changes.

        Fails gracefully when D-Bus is unavailable (e.g. bare Docker containers)
        by issuing a RuntimeWarning instead of raising.

        Note: when the app scheme is ``"system"`` (``Adw.ColorScheme.DEFAULT``),
        libadwaita already monitors gsettings internally and emits
        ``notify::dark`` automatically — no manual ``Adw.StyleManager`` call is
        needed in the handler.  The explicit connection here exists so the app
        can log/react to the event and for developer testing inside Docker via
        ``gsettings set org.gnome.desktop.interface color-scheme prefer-dark``.
        """
        try:
            settings = Gio.Settings.new("org.gnome.desktop.interface")
            settings.connect("changed::color-scheme", self._on_gsettings_changed)
            self._gsettings = settings  # keep ref — GC would drop the connection
        except GLib.Error as exc:
            warnings.warn(
                f"Could not connect to org.gnome.desktop.interface via gsettings "
                f"(D-Bus unavailable?): {exc}",
                RuntimeWarning,
                stacklevel=2,
            )

    def _on_gsettings_changed(self, _settings: Gio.Settings, _key: str) -> None:
        # When the user has an explicit light/dark override, system changes are
        # intentionally ignored — the local preference wins.
        # When scheme is "system", Adw.ColorScheme.DEFAULT lets libadwaita
        # follow gsettings automatically; it will emit notify::dark by itself.
        pass

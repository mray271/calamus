"""CalamusApplication — the top-level Gtk.Application."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib

from calamus.theme import ThemeManager
from calamus.window import CalamusWindow


class CalamusApplication(Adw.Application):
    """Primary application object."""

    def __init__(
        self,
        pipe_content: str | None = None,
        initial_files: list[str] | None = None,
    ) -> None:
        super().__init__(application_id="io.github.calamus.Calamus")
        GLib.set_application_name("Calamus")
        GLib.set_prgname("calamus")
        self._theme_manager: ThemeManager | None = None
        self._pipe_content = pipe_content
        self._initial_files: list[str] = initial_files or []

    def do_activate(self) -> None:
        if self._theme_manager is None:
            self._theme_manager = ThemeManager()

        window = self.get_active_window()
        if window is None:
            window = CalamusWindow(
                application=self,
                theme_manager=self._theme_manager,
                pipe_content=self._pipe_content,
                initial_files=self._initial_files,
            )
        window.present()

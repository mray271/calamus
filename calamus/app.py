"""CalamusApplication — the top-level Gtk.Application."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib

from calamus.window import CalamusWindow


class CalamusApplication(Adw.Application):
    """Primary application object."""

    def __init__(self) -> None:
        super().__init__(application_id="io.github.calamus.Calamus")
        GLib.set_application_name("Calamus")
        GLib.set_prgname("calamus")

    def do_activate(self) -> None:
        window = self.get_active_window()
        if window is None:
            window = CalamusWindow(application=self)
        window.present()

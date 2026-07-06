"""About dialog."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from calamus import MERMAID_VERSION, __version__


def show_about_dialog(parent) -> None:
    """Show the application about dialog."""
    dialog = Adw.AboutWindow.new()
    dialog.set_application_name("Calamus")
    dialog.set_version(__version__)
    dialog.set_developer_name("Calamus Contributors")
    dialog.set_license_type(Gtk.License.GPL_3_0)
    dialog.set_comments(
        f"A GTK4 Markdown editor for GNOME.\n\nPowered by Mermaid.js {MERMAID_VERSION}"
    )
    dialog.set_debug_info(f"Mermaid.js: {MERMAID_VERSION}")
    dialog.set_website("https://github.com/OWNER/calamus")
    dialog.set_issue_url("https://github.com/OWNER/calamus/issues")
    dialog.set_copyright("© 2024 Calamus Contributors")
    dialog.set_transient_for(parent)
    dialog.present()

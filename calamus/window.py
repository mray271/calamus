"""Main application window."""

from __future__ import annotations

import os

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from calamus.about import show_about_dialog
from calamus.directorytree import GtkDirectoryPane
from calamus.exporter import HtmlExporter, OdtExporter, PdfExporter
from calamus.formatting import DialogFormattingAction, FormattingRegistry
from calamus.preferences import FileConfigProvider, PreferencesDialog
from calamus.printer import GtkPrinter
from calamus.recentfiles import ConfigFileRecentFilesProvider
from calamus.tabs import AdwTabManager

GITHUB_RELEASES_URL = "https://github.com/OWNER/calamus/releases"
GITHUB_ISSUES_URL = "https://github.com/OWNER/calamus/issues"
MERMAID_DOCS_URL = "https://mermaid.js.org"


class CalamusWindow(Adw.ApplicationWindow):
    """Main Calamus window with menus and actions."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("Calamus")
        self.set_default_size(1200, 800)
        self._config_provider = FileConfigProvider()
        self._recent_files = ConfigFileRecentFilesProvider(self._config_provider)
        self._dir_pane_visible = True
        self._printer = GtkPrinter()
        self._build_ui()
        self._build_actions()

    def _build_ui(self) -> None:
        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(outer_box)

        header = Adw.HeaderBar()
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(self._build_menu())
        header.pack_end(menu_button)
        outer_box.append(header)

        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned.set_vexpand(True)
        outer_box.append(self.paned)

        self.dir_pane = GtkDirectoryPane()
        self.dir_pane.connect_file_activated(self._on_directory_file_activated)
        self.paned.set_start_child(self.dir_pane)
        self.paned.set_position(220)

        self.tab_manager = AdwTabManager(self)
        self.paned.set_end_child(self.tab_manager)

    def _build_menu(self) -> Gio.MenuModel:
        builder = Gtk.Builder.new_from_string(MENU_XML, -1)
        return builder.get_object("menubar")

    def _build_actions(self) -> None:
        app = self.get_application()
        if app is None:
            return
        for name, callback, accel in [
            ("new", self._on_new, "<primary>n"),
            ("open", self._on_open, "<primary>o"),
            ("save", self._on_save, "<primary>s"),
            ("save-as", self._on_save_as, "<primary><shift>s"),
            ("reload", self._on_reload, None),
            ("next-tab", self._on_next_tab, "<primary>Page_Down"),
            ("prev-tab", self._on_prev_tab, "<primary>Page_Up"),
            ("close-tab", self._on_close_tab, "<primary>w"),
            ("quit", self._on_quit, "<primary>q"),
            ("undo", self._on_undo, "<primary>z"),
            ("redo", self._on_redo, "<primary><shift>z"),
            ("cut", self._on_cut, "<primary>x"),
            ("copy", self._on_copy, "<primary>c"),
            ("paste", self._on_paste, "<primary>v"),
            ("goto-line", self._on_goto_line, "<primary>g"),
            ("find", self._on_find, "<primary>f"),
            ("preferences", self._on_preferences, None),
            ("export-html", self._on_export_html, None),
            ("export-pdf", self._on_export_pdf, None),
            ("export-odt", self._on_export_odt, None),
            ("print", self._on_print, "<primary>p"),
            ("print-preview", self._on_print_preview, "<primary><shift>p"),
            ("whats-new", self._on_whats_new, None),
            ("get-help-online", self._on_get_help_online, None),
            ("show-mermaid-version", self._on_show_mermaid_version, None),
            ("about", self._on_about, None),
        ]:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            app.add_action(action)
            if accel:
                app.set_accels_for_action(f"app.{name}", [accel])

        toggle = Gio.SimpleAction.new_stateful(
            "toggle-dir-pane", None, GLib.Variant.new_boolean(True)
        )
        toggle.connect("activate", self._on_toggle_dir_pane)
        app.add_action(toggle)

        for formatting_action in FormattingRegistry.get_all():
            action = Gio.SimpleAction.new(formatting_action.action_name, None)
            action.connect("activate", self._on_format_action_activated)
            app.add_action(action)

    def _get_current_text(self) -> str:
        editor = self.tab_manager.get_current_editor()
        return editor.get_text() if editor is not None else ""

    def _on_directory_file_activated(self, path: str) -> None:
        if path.endswith((".md", ".markdown", ".txt")):
            self.tab_manager.open_file(path)
            self._recent_files.add(path)

    def _on_new(self, _action: Gio.SimpleAction, _param: object) -> None:
        self.tab_manager.new_tab()

    def _on_open(self, _action: Gio.SimpleAction, _param: object) -> None:
        dialog = Gtk.FileDialog.new()
        file_filter = Gtk.FileFilter()
        file_filter.set_name("Markdown files")
        file_filter.add_pattern("*.md")
        file_filter.add_pattern("*.markdown")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(file_filter)
        dialog.set_filters(filters)
        dialog.open(self, None, self._on_open_response)

    def _on_open_response(self, dialog: Gtk.FileDialog, result: object) -> None:
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        if gfile is None:
            return
        path = gfile.get_path()
        if path is None:
            return
        self.tab_manager.open_file(path)
        self._recent_files.add(path)
        self.dir_pane.load_directory(os.path.dirname(path) or os.path.expanduser("~"))

    def _on_save(self, _action: Gio.SimpleAction, _param: object) -> None:
        self.tab_manager.save_current()

    def _on_save_as(self, _action: Gio.SimpleAction, _param: object) -> None:
        self.tab_manager.save_as_current(self)

    def _on_reload(self, _action: Gio.SimpleAction, _param: object) -> None:
        self.tab_manager.reload_current()

    def _on_next_tab(self, _action: Gio.SimpleAction, _param: object) -> None:
        self.tab_manager.next_tab()

    def _on_prev_tab(self, _action: Gio.SimpleAction, _param: object) -> None:
        self.tab_manager.prev_tab()

    def _on_close_tab(self, _action: Gio.SimpleAction, _param: object) -> None:
        self.tab_manager.close_current_tab()

    def _on_quit(self, _action: Gio.SimpleAction, _param: object) -> None:
        app = self.get_application()
        if app is not None:
            app.quit()

    def _on_toggle_dir_pane(self, action: Gio.SimpleAction, _param: object) -> None:
        self._dir_pane_visible = not self._dir_pane_visible
        self.dir_pane.set_visible(self._dir_pane_visible)
        action.set_state(GLib.Variant.new_boolean(self._dir_pane_visible))

    def _on_undo(self, _action: Gio.SimpleAction, _param: object) -> None:
        editor = self.tab_manager.get_current_editor()
        if editor is not None:
            editor.undo()

    def _on_redo(self, _action: Gio.SimpleAction, _param: object) -> None:
        editor = self.tab_manager.get_current_editor()
        if editor is not None:
            editor.redo()

    def _on_cut(self, _action: Gio.SimpleAction, _param: object) -> None:
        editor = self.tab_manager.get_current_editor()
        if editor is not None:
            editor.emit("cut-clipboard")

    def _on_copy(self, _action: Gio.SimpleAction, _param: object) -> None:
        editor = self.tab_manager.get_current_editor()
        if editor is not None:
            editor.emit("copy-clipboard")

    def _on_paste(self, _action: Gio.SimpleAction, _param: object) -> None:
        editor = self.tab_manager.get_current_editor()
        if editor is not None:
            editor.emit("paste-clipboard")

    def _on_goto_line(self, _action: Gio.SimpleAction, _param: object) -> None:
        editor = self.tab_manager.get_current_editor()
        if editor is not None:
            editor.show_goto_line_dialog(self)

    def _on_find(self, _action: Gio.SimpleAction, _param: object) -> None:
        editor = self.tab_manager.get_current_editor()
        if editor is not None:
            editor.toggle_find_bar()

    def _on_preferences(self, _action: Gio.SimpleAction, _param: object) -> None:
        PreferencesDialog(
            config_provider=self._config_provider,
            transient_for=self,
        ).present()

    def _on_export_html(self, _action: Gio.SimpleAction, _param: object) -> None:
        HtmlExporter().run_export_dialog(self, self._get_current_text())

    def _on_export_pdf(self, _action: Gio.SimpleAction, _param: object) -> None:
        PdfExporter().run_export_dialog(self, self._get_current_text())

    def _on_export_odt(self, _action: Gio.SimpleAction, _param: object) -> None:
        OdtExporter().run_export_dialog(self, self._get_current_text())

    def _on_print(self, _action: Gio.SimpleAction, _param: object) -> None:
        self._printer.print_document(self._get_current_text(), self)

    def _on_print_preview(self, _action: Gio.SimpleAction, _param: object) -> None:
        self._printer.print_preview(self._get_current_text(), self)

    def _on_format_action_activated(
        self,
        action: Gio.SimpleAction,
        _param: object,
    ) -> None:
        editor = self.tab_manager.get_current_editor()
        if editor is None:
            return
        formatting_action = FormattingRegistry.get_by_action_name(action.get_name())
        if formatting_action is None:
            return
        if isinstance(formatting_action, DialogFormattingAction):
            formatting_action.set_parent(self)
        formatting_action.apply(editor)

    def _on_whats_new(self, _action: Gio.SimpleAction, _param: object) -> None:
        Gtk.show_uri(self, GITHUB_RELEASES_URL, 0)

    def _on_get_help_online(self, _action: Gio.SimpleAction, _param: object) -> None:
        Gtk.show_uri(self, GITHUB_ISSUES_URL, 0)

    def _on_show_mermaid_version(
        self, _action: Gio.SimpleAction, _param: object
    ) -> None:
        Gtk.show_uri(self, MERMAID_DOCS_URL, 0)

    def _on_about(self, _action: Gio.SimpleAction, _param: object) -> None:
        show_about_dialog(self)


MENU_XML = """
<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <menu id="menubar">
    <submenu>
      <attribute name="label">File</attribute>
      <item><attribute name="label">New</attribute><attribute name="action">app.new</attribute></item>
      <item><attribute name="label">Open…</attribute><attribute name="action">app.open</attribute></item>
      <submenu>
        <attribute name="label">Open Recent</attribute>
        <item><attribute name="label">(No recent files)</attribute><attribute name="action">app.open</attribute></item>
      </submenu>
      <item><attribute name="label">Show Directory Tree Pane</attribute><attribute name="action">app.toggle-dir-pane</attribute></item>
      <item><attribute name="label">Reload</attribute><attribute name="action">app.reload</attribute></item>
      <item><attribute name="label">Save</attribute><attribute name="action">app.save</attribute></item>
      <item><attribute name="label">Save As…</attribute><attribute name="action">app.save-as</attribute></item>
      <item><attribute name="label">Next Tab</attribute><attribute name="action">app.next-tab</attribute></item>
      <item><attribute name="label">Previous Tab</attribute><attribute name="action">app.prev-tab</attribute></item>
      <item><attribute name="label">Close Tab</attribute><attribute name="action">app.close-tab</attribute></item>
      <submenu>
        <attribute name="label">Export</attribute>
        <item><attribute name="label">HTML</attribute><attribute name="action">app.export-html</attribute></item>
        <item><attribute name="label">PDF</attribute><attribute name="action">app.export-pdf</attribute></item>
        <item><attribute name="label">ODT</attribute><attribute name="action">app.export-odt</attribute></item>
      </submenu>
      <item><attribute name="label">Print…</attribute><attribute name="action">app.print</attribute></item>
      <item><attribute name="label">Print Preview…</attribute><attribute name="action">app.print-preview</attribute></item>
      <item><attribute name="label">Quit</attribute><attribute name="action">app.quit</attribute></item>
    </submenu>
    <submenu>
      <attribute name="label">Edit</attribute>
      <item><attribute name="label">Undo</attribute><attribute name="action">app.undo</attribute></item>
      <item><attribute name="label">Redo</attribute><attribute name="action">app.redo</attribute></item>
      <item><attribute name="label">Cut</attribute><attribute name="action">app.cut</attribute></item>
      <item><attribute name="label">Copy</attribute><attribute name="action">app.copy</attribute></item>
      <item><attribute name="label">Paste</attribute><attribute name="action">app.paste</attribute></item>
      <item><attribute name="label">Go to Line…</attribute><attribute name="action">app.goto-line</attribute></item>
      <item><attribute name="label">Find…</attribute><attribute name="action">app.find</attribute></item>
      <item><attribute name="label">Preferences</attribute><attribute name="action">app.preferences</attribute></item>
    </submenu>
    <submenu>
      <attribute name="label">Formatting</attribute>
      <submenu>
        <attribute name="label">Headings</attribute>
        <item><attribute name="label">Heading 1</attribute><attribute name="action">app.fmt-h1</attribute></item>
        <item><attribute name="label">Heading 2</attribute><attribute name="action">app.fmt-h2</attribute></item>
        <item><attribute name="label">Heading 3</attribute><attribute name="action">app.fmt-h3</attribute></item>
        <item><attribute name="label">Heading 4</attribute><attribute name="action">app.fmt-h4</attribute></item>
        <item><attribute name="label">Heading 5</attribute><attribute name="action">app.fmt-h5</attribute></item>
        <item><attribute name="label">Heading 6</attribute><attribute name="action">app.fmt-h6</attribute></item>
      </submenu>
      <item><attribute name="label">Bold</attribute><attribute name="action">app.fmt-bold</attribute></item>
      <item><attribute name="label">Italic</attribute><attribute name="action">app.fmt-italic</attribute></item>
      <item><attribute name="label">Bold &amp; Italic</attribute><attribute name="action">app.fmt-bold-italic</attribute></item>
      <item><attribute name="label">Strikethrough</attribute><attribute name="action">app.fmt-strikethrough</attribute></item>
      <item><attribute name="label">Inline Code</attribute><attribute name="action">app.fmt-inline-code</attribute></item>
      <item><attribute name="label">Code Block</attribute><attribute name="action">app.fmt-code-block</attribute></item>
      <item><attribute name="label">Blockquote</attribute><attribute name="action">app.fmt-blockquote</attribute></item>
      <item><attribute name="label">Ordered List</attribute><attribute name="action">app.fmt-ordered-list</attribute></item>
      <item><attribute name="label">Unordered List</attribute><attribute name="action">app.fmt-unordered-list</attribute></item>
      <item><attribute name="label">Horizontal Rule</attribute><attribute name="action">app.fmt-horizontal-rule</attribute></item>
      <item><attribute name="label">Link…</attribute><attribute name="action">app.fmt-link</attribute></item>
      <item><attribute name="label">Image…</attribute><attribute name="action">app.fmt-image</attribute></item>
    </submenu>
    <submenu>
      <attribute name="label">Help</attribute>
      <item><attribute name="label">What's New</attribute><attribute name="action">app.whats-new</attribute></item>
      <item><attribute name="label">Get Help Online</attribute><attribute name="action">app.get-help-online</attribute></item>
      <item><attribute name="label">Mermaid Diagrams: v11.5.0</attribute><attribute name="action">app.show-mermaid-version</attribute></item>
      <item><attribute name="label">About Calamus</attribute><attribute name="action">app.about</attribute></item>
    </submenu>
  </menu>
</interface>
"""

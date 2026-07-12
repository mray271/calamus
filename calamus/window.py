"""Main application window."""

from __future__ import annotations

import os
import sys

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
from calamus.theme import ThemeManager

GITHUB_RELEASES_URL = "https://github.com/mray271/calamus/releases"

# Extensions Calamus treats as openable text/Markdown files.
_TEXT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".md",
        ".markdown",
        ".mdown",
        ".mkd",
        ".mdx",
        ".txt",
        ".text",
        ".rst",
        ".adoc",
        ".asciidoc",
        ".org",
        ".wiki",
        ".tex",
        ".csv",
        ".log",
        ".yaml",
        ".yml",
        ".toml",
        ".json",
        ".xml",
        ".html",
        ".htm",
        ".css",
        ".js",
        ".py",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".rb",
        ".go",
        ".c",
        ".h",
        ".cpp",
        ".java",
        ".ts",
        ".rs",
        ".sql",
    }
)

# Number of bytes to sniff for binary detection on extensionless files.
_BINARY_SNIFF_BYTES = 512


def _is_openable(path: str) -> bool:
    """Return True if *path* should be opened in the editor.

    Checks the file extension first; for files with no recognised extension
    (including no extension at all) sniffs the first bytes for null bytes,
    which reliably identify binary content.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in _TEXT_EXTENSIONS:
        return True
    if ext:
        # Known non-text extension — reject without sniffing.
        return False
    # No extension: sniff for binary content.
    try:
        with open(path, "rb") as fh:
            return b"\x00" not in fh.read(_BINARY_SNIFF_BYTES)
    except OSError:
        return False


GITHUB_ISSUES_URL = "https://github.com/mray271/calamus/issues"
MERMAID_DOCS_URL = "https://mermaid.js.org"


class CalamusWindow(Adw.ApplicationWindow):
    """Main Calamus window with menus and actions."""

    def __init__(
        self,
        theme_manager: ThemeManager | None = None,
        pipe_content: str | None = None,
        initial_files: list[str] | None = None,
        preview_mode: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.set_title("Calamus")
        self.set_default_size(1200, 800)
        self._theme_manager = theme_manager or ThemeManager()
        self._config_provider = FileConfigProvider()
        self._recent_files = ConfigFileRecentFilesProvider(self._config_provider)
        self._dir_pane_visible = True
        self._editor_pane_visible = True
        self._preview_pane_visible = True
        self._confirmed_quit = False
        self._printer = GtkPrinter()
        self._pipe_content = pipe_content
        self._pipe_mode = pipe_content is not None
        self._pipe_saved_content: str | None = None
        self._preview_mode = preview_mode
        self._build_ui()
        self._build_actions()
        self.connect("close-request", self._on_close_request)
        if self._preview_mode:
            if self._pipe_content is not None:
                tab = self.tab_manager.get_current_tab()
                if tab is not None:
                    tab.load_content(self._pipe_content)
            elif initial_files:
                for path in initial_files:
                    self.tab_manager.open_file(path)
                    self._recent_files.add(path)
            self._enter_preview_mode()
        elif self._pipe_mode:
            self._enter_pipe_mode()
        elif initial_files:
            for path in initial_files:
                self.tab_manager.open_file(path)
                self._recent_files.add(path)

    def _build_ui(self) -> None:
        self.tab_manager = AdwTabManager(self)
        self.tab_manager.set_title_change_callback(self._update_window_title)
        tab_view = self.tab_manager.get_tab_view()

        # TabOverview must wrap all content so its "overview.open" action
        # is an ancestor of the TabButton in the header bar.
        self._tab_overview = Adw.TabOverview()
        self._tab_overview.set_view(tab_view)
        self.set_content(self._tab_overview)

        overview = self._tab_overview  # local alias for closures below

        inner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._content_box = inner_box
        overview.set_child(inner_box)

        # Header bar
        header = Adw.HeaderBar()

        for icon, action, tooltip in [
            ("document-new-symbolic", "app.new", "New file (Ctrl+N)"),
            ("document-open-symbolic", "app.open", "Open file (Ctrl+O)"),
            ("document-save-symbolic", "app.save", "Save (Ctrl+S)"),
        ]:
            btn = Gtk.Button(icon_name=icon)
            btn.set_action_name(action)
            btn.set_tooltip_text(tooltip)
            header.pack_start(btn)

        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(self._build_menu())
        header.pack_end(menu_button)

        self._btn_preview = Gtk.ToggleButton(icon_name="view-dual-symbolic")
        self._btn_preview.set_active(True)
        self._btn_preview.set_action_name("app.toggle-preview-pane")
        self._btn_preview.set_tooltip_text("Toggle preview pane (Ctrl+Shift+R)")
        header.pack_end(self._btn_preview)

        self._btn_editor = Gtk.ToggleButton(icon_name="document-edit-symbolic")
        self._btn_editor.set_active(True)
        self._btn_editor.set_action_name("app.toggle-editor-pane")
        self._btn_editor.set_tooltip_text("Toggle editor pane (Ctrl+Shift+E)")
        header.pack_end(self._btn_editor)

        self._btn_dir = Gtk.ToggleButton(icon_name="sidebar-show-symbolic")
        self._btn_dir.set_active(True)
        self._btn_dir.set_action_name("app.toggle-dir-pane")
        self._btn_dir.set_tooltip_text("Toggle directory tree (F9)")
        header.pack_end(self._btn_dir)

        tab_button = Adw.TabButton()
        tab_button.set_view(tab_view)
        tab_button.set_tooltip_text(
            "Show all open tabs — click a tab to switch, Esc to close"
        )
        tab_button.connect("clicked", lambda *_: overview.set_open(True))
        header.pack_end(tab_button)

        inner_box.append(header)

        # Tab bar spans the full width — above all three panes
        tab_bar = Adw.TabBar()
        tab_bar.set_view(tab_view)
        tab_bar.set_autohide(True)
        self._tab_bar = tab_bar
        inner_box.append(tab_bar)

        # Three-pane area
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.paned.set_vexpand(True)
        inner_box.append(self.paned)

        self.dir_pane = GtkDirectoryPane()
        self.dir_pane.connect_file_activated(self._on_directory_file_activated)
        self.paned.set_start_child(self.dir_pane)
        self.paned.set_position(220)

        self.paned.set_end_child(tab_view)

    def _build_menu(self) -> Gio.MenuModel:
        builder = Gtk.Builder.new_from_string(MENU_XML, -1)
        return builder.get_object("menubar")

    def _enter_pipe_mode(self) -> None:
        """Load piped content and configure the window for stdin→stdout editing."""
        tab = self.tab_manager.get_current_tab()
        if tab is not None:
            tab.load_content(self._pipe_content or "")

        self.set_title("Calamus — Pipe Mode")

        # Banner sits between the tab bar and the editor/preview panes.
        banner = Adw.Banner()
        banner.set_title(
            "Editing piped input — Ctrl+S to commit changes, close to emit saved text (or original if unsaved)"
        )
        banner.set_revealed(True)
        self._content_box.insert_child_after(banner, self._tab_bar)

        # Disable actions that don't make sense in a single-use pipe session.
        app = self.get_application()
        if app is not None:
            for name in ("new", "open", "save-as"):
                action = app.lookup_action(name)
                if action is not None:
                    action.set_enabled(False)

    def _enter_preview_mode(self) -> None:
        """Configure the window for read-only preview of content."""
        # Show only the preview pane.
        # We use emit to make sure UI state
        # is synced with the state of the toggle
        # buttons.
        if self._btn_editor.props.active:
            self._btn_editor.emit("clicked")
        if self._btn_dir.props.active:
            self._btn_dir.emit("clicked")

        self.tab_manager.set_all_editors_editable(False)

        self.set_title("Calamus \u2014 Preview Mode")

        app = self.get_application()
        if app is not None:
            for name in ("new", "open", "save", "save-as", "undo", "redo"):
                action = app.lookup_action(name)
                if action is not None:
                    action.set_enabled(False)

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
        app.set_accels_for_action("app.toggle-dir-pane", ["F9"])

        toggle_editor = Gio.SimpleAction.new_stateful(
            "toggle-editor-pane", None, GLib.Variant.new_boolean(True)
        )
        toggle_editor.connect("activate", self._on_toggle_editor_pane)
        app.add_action(toggle_editor)
        app.set_accels_for_action("app.toggle-editor-pane", ["<primary><shift>e"])

        toggle_preview = Gio.SimpleAction.new_stateful(
            "toggle-preview-pane", None, GLib.Variant.new_boolean(True)
        )
        toggle_preview.connect("activate", self._on_toggle_preview_pane)
        app.add_action(toggle_preview)
        app.set_accels_for_action("app.toggle-preview-pane", ["<primary><shift>r"])

        scheme_action = Gio.SimpleAction.new_stateful(
            "color-scheme",
            GLib.VariantType.new("s"),
            GLib.Variant.new_string(self._theme_manager.get_scheme()),
        )
        scheme_action.connect("activate", self._on_color_scheme_action)
        app.add_action(scheme_action)
        self._scheme_action = scheme_action

        for formatting_action in FormattingRegistry.get_all():
            action = Gio.SimpleAction.new(formatting_action.action_name, None)
            action.connect("activate", self._on_format_action_activated)
            app.add_action(action)

    def _get_current_text(self) -> str:
        editor = self.tab_manager.get_current_editor()
        return editor.get_text() if editor is not None else ""

    def _on_directory_file_activated(self, path: str) -> None:
        if _is_openable(path):
            self.tab_manager.open_file(path)
            self._recent_files.add(path)
        else:
            name = os.path.basename(path)
            dialog = Adw.AlertDialog.new(
                "Unsupported File Type",
                f"\u201c{name}\u201d appears to be a binary or unsupported file "
                "type.\n\nCalamus can only open plain-text and Markdown files.",
            )
            dialog.add_response("ok", "OK")
            dialog.set_default_response("ok")
            dialog.present(self)

    def _update_window_title(self) -> None:
        tab = self.tab_manager.get_current_tab()
        if tab is None:
            self.set_title("Calamus")
            return
        if self._preview_mode:
            self.set_title("Calamus \u2014 Preview Mode")
            return
        prefix = "\u25cf " if tab.modified else ""
        if self._pipe_mode:
            self.set_title(f"{prefix}Calamus \u2014 Pipe Mode")
        elif tab.file_path:
            name = os.path.basename(tab.file_path)
            self.set_title(f"{prefix}{name} \u2014 {tab.file_path}")
        else:
            self.set_title(f"{prefix}Untitled")

    def _on_new(self, _action: Gio.SimpleAction, _param: object) -> None:
        self.tab_manager.new_tab()

    def _on_open(self, _action: Gio.SimpleAction, _param: object) -> None:
        dialog = Gtk.FileDialog.new()

        md_filter = Gtk.FileFilter()
        md_filter.set_name("Markdown files (*.md, *.markdown)")
        md_filter.add_pattern("*.md")
        md_filter.add_pattern("*.markdown")
        md_filter.add_pattern("*.mdown")
        md_filter.add_pattern("*.mkd")
        md_filter.add_pattern("*.mdx")

        text_filter = Gtk.FileFilter()
        text_filter.set_name("All text files")
        for ext in sorted(_TEXT_EXTENSIONS):
            text_filter.add_pattern(f"*{ext}")

        all_filter = Gtk.FileFilter()
        all_filter.set_name("All files")
        all_filter.add_pattern("*")

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(md_filter)
        filters.append(text_filter)
        filters.append(all_filter)
        dialog.set_filters(filters)
        dialog.set_default_filter(md_filter)
        config = self._config_provider.load()
        initial_dir = (
            config.get("Files", "default_open_dir", fallback="") or os.getcwd()
        )
        dialog.set_initial_folder(Gio.File.new_for_path(initial_dir))
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
        if self._pipe_mode:
            editor = self.tab_manager.get_current_editor()
            if editor is not None:
                self._pipe_saved_content = editor.get_text()
            self.tab_manager.mark_current_saved()
        else:
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

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        if self._confirmed_quit:
            return False  # Already confirmed — allow close

        # Preview mode: read-only viewer — just close with no output.
        if self._preview_mode:
            return False

        # Pipe mode: emit saved text (or original input if no save occurred) to stdout.
        # Closing without saving reverts to the original input — same contract as Meld
        # used as a git mergetool.
        if self._pipe_mode:
            output = (
                self._pipe_saved_content
                if self._pipe_saved_content is not None
                else self._pipe_content or ""
            )
            sys.stdout.write(output)
            sys.stdout.flush()
            return False

        tab_count = self.tab_manager.get_tab_count()
        unsaved = self.tab_manager.get_unsaved_tabs()

        # Single clean tab — no friction needed.
        if tab_count == 1 and not unsaved:
            return False

        if unsaved:
            heading = "Unsaved Changes"
            body = "At least one file has unsaved changes. Exit Calamus?"
            quit_label = "Exit Without Saving"
            appearance = Adw.ResponseAppearance.DESTRUCTIVE
        else:
            heading = "Exit Calamus?"
            body = f"{tab_count} files are open. Exit Calamus?"
            quit_label = "Exit"
            appearance = Adw.ResponseAppearance.DEFAULT

        dialog = Adw.AlertDialog.new(heading, body)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("quit", quit_label)
        dialog.set_response_appearance("quit", appearance)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_quit_dialog_response)
        dialog.present(self)
        return True  # Block the close until the user decides

    def _on_quit_dialog_response(self, _dialog: Adw.AlertDialog, response: str) -> None:
        if response == "quit":
            self._confirmed_quit = True
            self.close()

    def _on_color_scheme_action(
        self, action: Gio.SimpleAction, param: GLib.Variant
    ) -> None:
        scheme = param.get_string()
        action.set_state(GLib.Variant.new_string(scheme))
        self._theme_manager.set_scheme(scheme)

    def _on_toggle_dir_pane(self, action: Gio.SimpleAction, _param: object) -> None:
        self._dir_pane_visible = not self._dir_pane_visible
        self.dir_pane.set_visible(self._dir_pane_visible)
        action.set_state(GLib.Variant.new_boolean(self._dir_pane_visible))

    def _on_toggle_editor_pane(self, action: Gio.SimpleAction, _param: object) -> None:
        self._editor_pane_visible = not self._editor_pane_visible
        self.tab_manager.set_editor_pane_visible(self._editor_pane_visible)
        action.set_state(GLib.Variant.new_boolean(self._editor_pane_visible))

    def _on_toggle_preview_pane(self, action: Gio.SimpleAction, _param: object) -> None:
        self._preview_pane_visible = not self._preview_pane_visible
        self.tab_manager.set_preview_pane_visible(self._preview_pane_visible)
        action.set_state(GLib.Variant.new_boolean(self._preview_pane_visible))

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
            editor.get_widget().emit("cut-clipboard")

    def _on_copy(self, _action: Gio.SimpleAction, _param: object) -> None:
        editor = self.tab_manager.get_current_editor()
        if editor is not None:
            editor.get_widget().emit("copy-clipboard")

    def _on_paste(self, _action: Gio.SimpleAction, _param: object) -> None:
        editor = self.tab_manager.get_current_editor()
        if editor is not None:
            editor.get_widget().emit("paste-clipboard")

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
            theme_manager=self._theme_manager,
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

"""Markdown editor abstractions and implementations."""

from __future__ import annotations

from abc import ABC, ABCMeta, abstractmethod
import configparser

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, GtkSource, Pango


class AbstractEditor(ABC):
    """Abstract editor widget interface."""

    @abstractmethod
    def get_text(self) -> str:
        """Return the full editor contents."""

    @abstractmethod
    def set_text(self, text: str) -> None:
        """Replace the editor contents."""

    @abstractmethod
    def get_selection(self) -> tuple[str, bool]:
        """Return selected text and whether a selection exists."""

    @abstractmethod
    def replace_selection(self, new_text: str) -> None:
        """Replace the current selection."""

    @abstractmethod
    def insert_at_cursor(self, text: str) -> None:
        """Insert text at the cursor."""

    @abstractmethod
    def undo(self) -> None:
        """Undo the last operation."""

    @abstractmethod
    def redo(self) -> None:
        """Redo the last undone operation."""

    @abstractmethod
    def show_goto_line_dialog(self, parent: Gtk.Window) -> None:
        """Show a go-to-line dialog."""

    @abstractmethod
    def toggle_find_bar(self) -> None:
        """Toggle the find UI."""

    @abstractmethod
    def configure_from_prefs(self, config: configparser.ConfigParser) -> None:
        """Apply preferences to the editor widget."""

    @abstractmethod
    def get_widget(self) -> Gtk.Widget:
        """Return the underlying GTK widget."""


class MarkdownEditor(AbstractEditor):
    """Concrete GtkSource-based Markdown editor."""

    def __init__(self) -> None:
        super().__init__()
        self._view = GtkSource.View()  # Create a GtkSource.View instance
        self._find_bar: Gtk.Widget | None = None
        self._find_revealer: Gtk.Revealer | None = None
        self._css_provider = Gtk.CssProvider()

    def _setup_buffer(self) -> None:
        language_manager = GtkSource.LanguageManager.get_default()
        language = language_manager.get_language("markdown")
        buffer = GtkSource.Buffer()
        if language is not None:
            buffer.set_language(language)
        buffer.set_highlight_syntax(True)
        buffer.set_undo_manager(None)
        self._view.set_buffer(buffer)

    def _setup_view(self) -> None:
        self.set_show_line_numbers(True)
        self.set_auto_indent(True)
        self.set_tab_width(4)
        self.set_insert_spaces_instead_of_tabs(True)
        self.set_highlight_current_line(True)
        self.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._apply_font(Pango.FontDescription.from_string("Monospace 11"))
        self.set_monospace(True)

    def _apply_font(self, font_description: Pango.FontDescription) -> None:
        family = font_description.get_family() or "Monospace"
        size_pt = max(1, font_description.get_size() // Pango.SCALE)
        css = f"textview.calamus-editor {{ font-family: {family}; font-size: {size_pt}pt; }}"
        self._css_provider.load_from_string(css)
        self._view.add_css_class("calamus-editor")
        Gtk.StyleContext.add_provider_for_display(
            self._view.get_display(),
            self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def get_widget(self) -> GtkSource.View:
        return self._view

    def get_buffer(self) -> GtkSource.Buffer:
        return self._view.get_buffer()

    def get_text(self) -> str:
        buffer = self._view.get_buffer()
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

    def set_text(self, text: str) -> None:
        self.get_buffer().set_text(text)

    def get_selection(self) -> tuple[str, bool]:
        buffer = self.get_buffer()
        if buffer.get_has_selection():
            start, end = buffer.get_selection_bounds()
            return buffer.get_text(start, end, True), True
        return "", False

    def replace_selection(self, new_text: str) -> None:
        buffer = self.get_buffer()
        buffer.begin_user_action()
        buffer.delete_selection(True, True)
        buffer.insert_at_cursor(new_text)
        buffer.end_user_action()

    def insert_at_cursor(self, text: str) -> None:
        buffer = self.get_buffer()
        buffer.begin_user_action()
        buffer.insert_at_cursor(text)
        buffer.end_user_action()

    def undo(self) -> None:
        buffer = self.get_buffer()
        if buffer.props.can_undo:
            buffer.undo()

    def redo(self) -> None:
        buffer = self.get_buffer()
        if buffer.props.can_redo:
            buffer.redo()

    def show_goto_line_dialog(self, parent: Gtk.Window) -> None:
        dialog = Adw.MessageDialog.new(parent, "Go to Line", None)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("go", "Go")
        dialog.set_default_response("go")
        dialog.set_close_response("cancel")

        entry = Gtk.Entry()
        entry.set_placeholder_text("Line number")
        entry.set_input_purpose(Gtk.InputPurpose.NUMBER)
        dialog.set_extra_child(entry)

        def on_response(_dialog: Adw.MessageDialog, response: str) -> None:
            if response != "go":
                return
            try:
                line = int(entry.get_text()) - 1
            except ValueError:
                return
            buffer = self.get_buffer()
            iterator = buffer.get_iter_at_line(max(0, line))
            buffer.place_cursor(iterator)
            self._view.scroll_to_iter(iterator, 0.1, True, 0.0, 0.5)

        dialog.connect("response", on_response)
        dialog.present()

    def toggle_find_bar(self) -> None:
        if self._find_revealer is not None:
            self._find_revealer.set_reveal_child(
                not self._find_revealer.get_reveal_child()
            )

    def configure_from_prefs(self, config: configparser.ConfigParser) -> None:
        font_family = config.get("Editor", "font_family", fallback="Monospace")
        font_size = config.getint("Editor", "font_size", fallback=11)
        font_description = Pango.FontDescription.from_string(
            f"{font_family} {font_size}"
        )
        self._apply_font(font_description)
        self._view.set_tab_width(config.getint("Editor", "tab_width", fallback=4))
        self._view.set_insert_spaces_instead_of_tabs(
            config.getboolean("Editor", "use_spaces", fallback=True)
        )
        self._view.set_show_line_numbers(
            config.getboolean("Editor", "show_line_numbers", fallback=True)
        )
        self._view.set_wrap_mode(
            Gtk.WrapMode.WORD_CHAR
            if config.getboolean("Editor", "word_wrap", fallback=True)
            else Gtk.WrapMode.NONE
        )
        self._view.set_highlight_current_line(
            config.getboolean("Editor", "highlight_current_line", fallback=True)
        )

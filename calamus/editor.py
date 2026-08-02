"""Markdown editor abstractions and implementations."""

from __future__ import annotations

import configparser
import os
from abc import ABC, ABCMeta, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from calamus.search import SearchState

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, GtkSource, Pango

# Register Calamus custom style schemes (calamus-adwaita, calamus-adwaita-dark)
# so the StyleSchemeManager can find them before any MarkdownEditor is created.
_STYLES_DIR = os.path.join(os.path.dirname(__file__), "resources", "styles")
GtkSource.StyleSchemeManager.get_default().append_search_path(_STYLES_DIR)


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
    def goto_line(self, line: int, col: int = 0) -> None:
        """Jump to the given 0-based *line* and *col*, selecting the full line."""

    @abstractmethod
    def zoom_by(self, factor: float) -> None:
        """Scale editor font size by a factor."""

    @abstractmethod
    def reset_zoom(self) -> None:
        """Reset editor zoom to its default."""

    @abstractmethod
    def configure_from_prefs(self, config: configparser.ConfigParser) -> None:
        """Apply preferences to the editor widget."""

    @abstractmethod
    def get_widget(self) -> Gtk.Widget:
        """Return the underlying GTK widget."""

    @abstractmethod
    def set_editable(self, editable: bool) -> None:
        """Set whether the editor is editable."""

    @abstractmethod
    def find_next(self, state: "SearchState") -> bool:  # noqa: F821
        """Find the next occurrence matching *state*.

        Returns True if a match was found and selected, False otherwise.
        """

    @abstractmethod
    def find_previous(self, state: "SearchState") -> bool:  # noqa: F821
        """Find the previous occurrence matching *state*.

        Returns True if a match was found and selected, False otherwise.
        """

    @abstractmethod
    def replace_current(
        self, replacement: str, state: "SearchState"
    ) -> bool:  # noqa: F821
        """Replace the currently-selected match with *replacement*.

        Returns True if a replacement was performed.
        """

    @abstractmethod
    def replace_all(
        self, replacement: str, scope: str, state: "SearchState"  # noqa: F821
    ) -> int:
        """Replace all occurrences of the search term with *replacement*.

        *scope* is one of ``"window"``, ``"selection"``.
        Returns the number of replacements made.
        """

    @abstractmethod
    def replace_and_find(
        self, replacement: str, state: "SearchState"
    ) -> bool:  # noqa: F821
        """Replace the current match then immediately find the next one.

        Returns True if the replacement was performed.
        """


class MarkdownEditor(AbstractEditor):
    """Concrete GtkSource-based Markdown editor."""

    _MIN_FONT_SIZE_PT = 8.0
    _MAX_FONT_SIZE_PT = 48.0

    def __init__(self) -> None:
        super().__init__()
        self._view = GtkSource.View()
        self._find_bar: Gtk.Widget | None = None
        self._find_revealer: Gtk.Revealer | None = None
        self._css_provider = Gtk.CssProvider()
        self._setup_buffer()
        self._setup_view()
        self._style_manager = Adw.StyleManager.get_default()
        self._apply_style_scheme()
        self._style_manager.connect("notify::dark", self._on_dark_changed)
        self._font_family = "Monospace"
        self.current_font_size = 11.0
        self.default_font_size = self.current_font_size
        self.default_font_family = self._font_family

    def _setup_buffer(self) -> None:
        language_manager = GtkSource.LanguageManager.get_default()
        language = language_manager.get_language("markdown")
        buffer = GtkSource.Buffer()
        if language is not None:
            buffer.set_language(language)
        buffer.set_highlight_syntax(True)
        self._view.set_buffer(buffer)
        # Build a SearchContext bound to this buffer so we can reuse it across
        # all find/replace calls without recreating settings each time.
        self._search_settings = GtkSource.SearchSettings()
        self._search_context = GtkSource.SearchContext.new(
            buffer, self._search_settings
        )

    def _setup_view(self) -> None:
        self._view.set_show_line_numbers(True)
        self._view.set_auto_indent(True)
        self._view.set_tab_width(4)
        self._view.set_insert_spaces_instead_of_tabs(True)
        self._view.set_highlight_current_line(True)
        self._view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._apply_font(Pango.FontDescription.from_string("Monospace 11"))
        self._view.set_monospace(True)

    def _apply_style_scheme(self) -> None:
        """Switch the GtkSourceView style scheme to match the current dark/light state."""
        dark = self._style_manager.get_dark()
        scheme_manager = GtkSource.StyleSchemeManager.get_default()
        # Prefer Calamus schemes (full Markdown token coverage), fall back to
        # the built-in Adwaita variants, then generic fallbacks.
        candidates = (
            ["calamus-adwaita-dark", "Adwaita-dark", "oblivion", "classic-dark"]
            if dark
            else ["calamus-adwaita", "Adwaita", "classic", "tango"]
        )
        scheme = next(
            (
                scheme_manager.get_scheme(name)
                for name in candidates
                if scheme_manager.get_scheme(name) is not None
            ),
            None,
        )
        if scheme is not None:
            self._view.get_buffer().set_style_scheme(scheme)

    def _on_dark_changed(
        self, _style_manager: Adw.StyleManager, _param: object
    ) -> None:
        self._apply_style_scheme()

    def _apply_font(self, font_description: Pango.FontDescription) -> None:
        family = font_description.get_family() or self._font_family
        size_pt = max(
            self._MIN_FONT_SIZE_PT,
            min(
                self._MAX_FONT_SIZE_PT,
                font_description.get_size() / Pango.SCALE,
            ),
        )
        self._font_family = family
        self.current_font_size = size_pt
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

    def set_editable(self, editable: bool) -> None:
        self._view.set_editable(editable)
        self._view.set_cursor_visible(editable)

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
        from calamus.search_dialogs import GotoLineDialog

        GotoLineDialog(self, parent)

    def goto_line(self, line: int, col: int = 0) -> None:
        """Jump to 0-based *line*/*col* and select the full line."""
        buffer = self.get_buffer()
        _ok, start = buffer.get_iter_at_line_offset(line, col)
        end = start.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        buffer.select_range(start, end)
        self._view.scroll_to_iter(start, 0.1, True, 0.0, 0.5)

    def toggle_find_bar(self) -> None:
        if self._find_revealer is not None:
            self._find_revealer.set_reveal_child(
                not self._find_revealer.get_reveal_child()
            )

    # ------------------------------------------------------------------
    # Search / Replace helpers
    # ------------------------------------------------------------------

    def _update_search_highlighting(self, state: SearchState) -> None:
        """Sync GtkSource.SearchSettings for live in-editor highlighting."""
        self._search_settings.set_search_text(
            state.find_history[-1] if state.find_history else ""
        )
        self._search_settings.set_regex_enabled(state.use_regex)
        self._search_settings.set_case_sensitive(state.case_sensitive)
        self._search_settings.set_at_word_boundaries(state.whole_word)

    def _find_in_text(
        self,
        needle: str,
        haystack: str,
        from_offset: int,
        use_regex: bool,
        case_sensitive: bool,
        whole_word: bool,
        backward: bool = False,
    ) -> tuple[int, int] | None:
        """Return (start, end) offsets of the next/prev match, or None."""
        import re

        flags = re.MULTILINE
        if not case_sensitive:
            flags |= re.IGNORECASE
        if use_regex:
            pattern = needle
        else:
            pattern = re.escape(needle)
        if whole_word:
            pattern = r"\b" + pattern + r"\b"
        try:
            compiled = re.compile(pattern, flags)
        except re.error:
            return None

        if backward:
            # Search from start up to from_offset, keep last match
            matches = list(compiled.finditer(haystack, 0, from_offset))
            if not matches:
                # Wrap around: search whole buffer
                matches = list(compiled.finditer(haystack))
                if not matches:
                    return None
            m = matches[-1]
        else:
            m = compiled.search(haystack, from_offset)
            if m is None:
                # Wrap around from the beginning
                m = compiled.search(haystack, 0, from_offset)
            if m is None:
                return None
        return m.start(), m.end()

    def find_next(self, state: SearchState) -> bool:
        """Find and select the next occurrence. Returns True on match."""
        self._update_search_highlighting(state)
        needle = state.find_history[-1] if state.find_history else ""
        if not needle:
            return False
        buffer = self.get_buffer()
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        # Advance past the end of any current selection so we don't re-find it.
        if buffer.get_has_selection():
            _sel_start, sel_end = buffer.get_selection_bounds()
            cursor_offset = sel_end.get_offset()
        else:
            cursor_offset = buffer.get_iter_at_mark(buffer.get_insert()).get_offset()
        result = self._find_in_text(
            needle,
            text,
            cursor_offset,
            state.use_regex,
            state.case_sensitive,
            state.whole_word,
        )
        if result is None:
            return False
        start_off, end_off = result
        start_iter = buffer.get_iter_at_offset(start_off)
        end_iter = buffer.get_iter_at_offset(end_off)
        buffer.select_range(start_iter, end_iter)
        self._view.scroll_to_iter(start_iter, 0.1, True, 0.0, 0.5)
        return True

    def find_previous(self, state: SearchState) -> bool:
        """Find and select the previous occurrence. Returns True on match."""
        self._update_search_highlighting(state)
        needle = state.find_history[-1] if state.find_history else ""
        if not needle:
            return False
        buffer = self.get_buffer()
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        # Search before the start of any current selection so we don't re-find it.
        if buffer.get_has_selection():
            sel_start, _sel_end = buffer.get_selection_bounds()
            cursor_offset = sel_start.get_offset()
        else:
            cursor_offset = buffer.get_iter_at_mark(buffer.get_insert()).get_offset()
        result = self._find_in_text(
            needle,
            text,
            cursor_offset,
            state.use_regex,
            state.case_sensitive,
            state.whole_word,
            backward=True,
        )
        if result is None:
            return False
        start_off, end_off = result
        start_iter = buffer.get_iter_at_offset(start_off)
        end_iter = buffer.get_iter_at_offset(end_off)
        buffer.select_range(start_iter, end_iter)
        self._view.scroll_to_iter(start_iter, 0.1, True, 0.0, 0.5)
        return True

    def replace_current(self, replacement: str, state: SearchState) -> bool:
        """Replace the currently-selected match. Returns True if replaced."""
        buffer = self.get_buffer()
        if not buffer.get_has_selection():
            return False
        buffer.begin_user_action()
        buffer.delete_selection(True, True)
        buffer.insert_at_cursor(replacement)
        buffer.end_user_action()
        return True

    def replace_all(self, replacement: str, scope: str, state: SearchState) -> int:
        """Replace all occurrences. *scope*: ``"window"`` or ``"selection"``."""
        import re

        needle = state.find_history[-1] if state.find_history else ""
        if not needle:
            return 0
        flags = re.MULTILINE
        if not state.case_sensitive:
            flags |= re.IGNORECASE
        if state.use_regex:
            pattern = needle
        else:
            pattern = re.escape(needle)
        if state.whole_word:
            pattern = r"\b" + pattern + r"\b"
        try:
            compiled = re.compile(pattern, flags)
        except re.error:
            return 0

        buffer = self.get_buffer()
        if scope == "selection" and buffer.get_has_selection():
            sel_start, sel_end = buffer.get_selection_bounds()
            region_text = buffer.get_text(sel_start, sel_end, True)
            new_text, count = compiled.subn(replacement, region_text)
            if count:
                buffer.begin_user_action()
                buffer.delete(sel_start, sel_end)
                buffer.insert(sel_start, new_text)
                buffer.end_user_action()
            return count
        full_text = buffer.get_text(
            buffer.get_start_iter(), buffer.get_end_iter(), True
        )
        new_text, count = compiled.subn(replacement, full_text)
        if count:
            buffer.begin_user_action()
            buffer.set_text(new_text)
            buffer.end_user_action()
        return count

    def replace_and_find(self, replacement: str, state: SearchState) -> bool:
        """Replace the current match then find the next one."""
        self.replace_current(replacement, state)
        return self.find_next(state)

    def zoom_by(self, factor: float) -> None:
        if factor <= 0:
            return
        font_size = round(self.current_font_size * factor, 1)
        font_description = Pango.FontDescription.from_string(
            f"{self._font_family} {font_size}"
        )
        self._apply_font(font_description)

    def reset_zoom(self) -> None:
        font_description = Pango.FontDescription.from_string(
            f"{self.default_font_family} {self.default_font_size}"
        )
        self._apply_font(font_description)

    def configure_from_prefs(self, config: configparser.ConfigParser) -> None:
        font_family = config.get("Editor", "font_family", fallback="Monospace")
        font_size = float(config.getint("Editor", "font_size", fallback=11))
        self.default_font_family = font_family
        self.default_font_size = font_size
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

"""Tab abstractions and Adwaita-backed implementation."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from calamus.editor import AbstractEditor, MarkdownEditor
from calamus.preferences import FileConfigProvider
from calamus.preview import AbstractPreview, create_preview

# Files larger than this will be refused with an error dialog rather than
# loaded.  Markdown syntax highlighting and live preview rendering become
# unacceptably slow above this threshold; 20 MB matches VS Code's own
# large-file optimisation cutoff.
LARGE_FILE_SIZE_BYTES: int = 20 * 1024 * 1024  # 20 MB


class FileTooLargeError(Exception):
    """Raised when a file exceeds LARGE_FILE_SIZE_BYTES."""

    def __init__(self, path: str, size: int, limit: int) -> None:
        self.path = path
        self.size = size
        self.limit = limit
        size_mb = size / (1024 * 1024)
        limit_mb = limit / (1024 * 1024)
        super().__init__(
            f"{os.path.basename(path)!r} is {size_mb:.1f} MB "
            f"(limit is {limit_mb:.0f} MB)"
        )


class AbstractTab(ABC):
    """Defines a tab interface."""

    @property
    @abstractmethod
    def title(self) -> str:
        """Return the tab title."""

    @property
    @abstractmethod
    def file_path(self) -> str | None:
        """Return the active file path."""

    @property
    @abstractmethod
    def modified(self) -> bool:
        """Return whether the tab has unsaved changes."""

    @abstractmethod
    def get_editor(self) -> AbstractEditor:
        """Return the tab's editor."""

    @abstractmethod
    def save(self) -> bool:
        """Save the tab contents."""

    @abstractmethod
    def mark_saved(self) -> None:
        """Mark the tab as unmodified without writing to disk."""

    @abstractmethod
    def reload(self) -> None:
        """Reload the tab contents from disk."""

    @abstractmethod
    def load_file(self, path: str) -> None:
        """Load file contents into the tab."""


@AbstractTab.register
class EditorTab(Gtk.Box):
    """Concrete editor tab implementation."""

    def __init__(self, file_path: str | None = None, on_open_path=None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._file_path = file_path
        self._modified = False
        self.search_bar = Gtk.SearchBar()
        self.search_entry = Gtk.SearchEntry()
        self.editor: MarkdownEditor = MarkdownEditor()
        self.preview: AbstractPreview = create_preview(on_open_path=on_open_path)
        self._preview_timer_id: int | None = None
        config = FileConfigProvider().load()
        self._preview_delay_ms: int = config.getint(
            "Preview", "refresh_delay_ms", fallback=500
        )
        self._build_ui()
        self.editor.configure_from_prefs(config)
        if file_path is not None:
            self.load_file(file_path)
        else:
            self.preview.update("")

    @property
    def title(self) -> str:
        name = os.path.basename(self._file_path) if self._file_path else "Untitled"
        return f"{'*' if self._modified else ''}{name}"

    @property
    def file_path(self) -> str | None:
        return self._file_path

    @file_path.setter
    def file_path(self, value: str | None) -> None:
        self._file_path = value
        self.preview.set_file_path(value)

    @property
    def modified(self) -> bool:
        return self._modified

    def get_editor(self) -> AbstractEditor:
        return self.editor

    def save(self) -> bool:
        if self._file_path is None:
            return False
        try:
            with open(self._file_path, "w", encoding="utf-8") as handle:
                handle.write(self.editor.get_text())
        except OSError:
            return False
        self._modified = False
        return True

    def mark_saved(self) -> None:
        """Clear the modified flag without writing to disk."""
        self._modified = False

    def reload(self) -> None:
        if self._file_path is not None:
            self.load_file(self._file_path)

    def load_content(self, text: str, preview_base_path: str | None = None) -> None:
        """Load a string directly into the editor without marking the tab modified."""
        if preview_base_path is not None:
            self.preview.set_base_path(preview_base_path)
        elif self._file_path is not None:
            self.preview.set_file_path(self._file_path)
        self.editor.set_text(text)
        self.preview.update(text)
        self._modified = False

    def load_file(self, path: str) -> None:
        self._file_path = path
        self.preview.set_file_path(path)
        try:
            file_size = os.path.getsize(path)
            if file_size > LARGE_FILE_SIZE_BYTES:
                raise FileTooLargeError(path, file_size, LARGE_FILE_SIZE_BYTES)
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()
        except FileTooLargeError:
            raise
        except OSError as error:
            content = f"Error loading file: {error}"
            self.editor.set_text(content)
            self.preview.update(content)
            self._modified = False
            return
        self.editor.set_text(content)
        self.preview.update(content)
        self._modified = False

    def set_editor_visible(self, visible: bool) -> None:
        self._scroll_editor.set_visible(visible)

    def set_preview_visible(self, visible: bool) -> None:
        self._scroll_preview.set_visible(visible)

    def _build_ui(self) -> None:
        self.search_bar.set_child(self.search_entry)
        self.search_bar.connect_entry(self.search_entry)
        self.append(self.search_bar)

        self._paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._paned.set_vexpand(True)
        self.append(self._paned)

        self._scroll_editor = Gtk.ScrolledWindow()
        self._scroll_editor.set_child(self.editor.get_widget())
        self._paned.set_start_child(self._scroll_editor)

        self._scroll_preview = Gtk.ScrolledWindow()
        self._scroll_preview.set_child(self.preview.get_widget())
        self._paned.set_end_child(self._scroll_preview)

        self.editor.get_buffer().connect("changed", self._on_buffer_changed)

    def _on_buffer_changed(self, _buffer: object) -> None:
        self._modified = True
        # Debounce: cancel any pending preview refresh and restart the timer.
        # The preview only updates after the user pauses for _preview_delay_ms.
        if self._preview_timer_id is not None:
            GLib.source_remove(self._preview_timer_id)
        self._preview_timer_id = GLib.timeout_add(
            self._preview_delay_ms, self._flush_preview
        )

    def _flush_preview(self) -> bool:
        self._preview_timer_id = None
        self.preview.update(self.editor.get_text())
        return GLib.SOURCE_REMOVE


class AbstractTabManager(ABC):
    """Defines tab-management behavior."""

    @abstractmethod
    def get_widget(self) -> Gtk.Widget:
        """Return the widget backing the tab manager."""

    @abstractmethod
    def new_tab(self, file_path: str | None = None) -> AbstractTab:
        """Create a new tab."""

    @abstractmethod
    def open_file(self, path: str) -> None:
        """Open a file in a tab."""

    @abstractmethod
    def get_current_tab(self) -> AbstractTab | None:
        """Return the active tab."""

    @abstractmethod
    def get_current_editor(self) -> AbstractEditor | None:
        """Return the active editor."""

    @abstractmethod
    def save_current(self) -> None:
        """Save the current tab."""

    @abstractmethod
    def save_as_current(self, parent: Gtk.Window) -> None:
        """Save the current tab under a new name."""

    @abstractmethod
    def reload_current(self) -> None:
        """Reload the current tab from disk."""

    @abstractmethod
    def close_current_tab(self) -> None:
        """Close the current tab."""

    @abstractmethod
    def next_tab(self) -> None:
        """Select the next tab."""

    @abstractmethod
    def prev_tab(self) -> None:
        """Select the previous tab."""


class AdwTabManager(AbstractTabManager):
    """Adwaita TabView-backed tab manager (composition — AdwTabView is final)."""

    def __init__(self, window: Gtk.Window) -> None:
        self._window = window
        self._tab_view = Adw.TabView()
        self._tab_view.set_vexpand(True)
        self._editor_visible = True
        self._preview_visible = True
        self._on_title_changed: object = None
        self._tab_view.connect(
            "notify::selected-page", lambda *_: self._notify_title_changed()
        )
        self.new_tab()

    def get_widget(self) -> Gtk.Widget:
        return self._tab_view

    def get_tab_view(self) -> Adw.TabView:
        return self._tab_view

    def set_title_change_callback(self, callback: object) -> None:
        self._on_title_changed = callback

    def _notify_title_changed(self) -> None:
        if self._on_title_changed is not None:
            self._on_title_changed()

    def new_tab(self, file_path: str | None = None) -> AbstractTab:
        tab = EditorTab(file_path, on_open_path=self.open_file)
        tab.set_editor_visible(self._editor_visible)
        tab.set_preview_visible(self._preview_visible)
        page = self._tab_view.append(tab)
        page.set_title(tab.title)

        def _on_buffer_changed(*_args):
            page.set_title(tab.title)
            self._notify_title_changed()

        tab.editor.get_buffer().connect("changed", _on_buffer_changed)
        self._tab_view.set_selected_page(page)
        return tab

    def get_tab_count(self) -> int:
        return self._tab_view.get_n_pages()

    def get_unsaved_tabs(self) -> list[str]:
        """Return display names of all tabs with unsaved changes."""
        names = []
        for index in range(self._tab_view.get_n_pages()):
            child = self._tab_view.get_nth_page(index).get_child()
            if isinstance(child, EditorTab) and child.modified:
                names.append(
                    os.path.basename(child.file_path) if child.file_path else "Untitled"
                )
        return names

    def set_editor_pane_visible(self, visible: bool) -> None:
        self._editor_visible = visible
        for index in range(self._tab_view.get_n_pages()):
            child = self._tab_view.get_nth_page(index).get_child()
            if isinstance(child, EditorTab):
                child.set_editor_visible(visible)

    def set_preview_pane_visible(self, visible: bool) -> None:
        self._preview_visible = visible
        for index in range(self._tab_view.get_n_pages()):
            child = self._tab_view.get_nth_page(index).get_child()
            if isinstance(child, EditorTab):
                child.set_preview_visible(visible)

    def open_file(self, path: str) -> None:
        try:
            file_size = os.path.getsize(path)
        except OSError:
            file_size = 0
        if file_size > LARGE_FILE_SIZE_BYTES:
            self._show_file_too_large_dialog(path, file_size)
            return
        # Switch to already-open tab if the file is loaded elsewhere.
        for index in range(self._tab_view.get_n_pages()):
            page = self._tab_view.get_nth_page(index)
            child = page.get_child()
            if isinstance(child, EditorTab) and child.file_path == path:
                self._tab_view.set_selected_page(page)
                return
        # Replace a sole clean Untitled tab rather than opening alongside it.
        if self._tab_view.get_n_pages() == 1:
            only = self._tab_view.get_nth_page(0).get_child()
            if (
                isinstance(only, EditorTab)
                and only.file_path is None
                and not only.modified
            ):
                only.load_file(path)
                self._tab_view.get_nth_page(0).set_title(only.title)
                self._notify_title_changed()
                return
        self.new_tab(path)

    def get_current_tab(self) -> AbstractTab | None:
        page = self._tab_view.get_selected_page()
        if page is None:
            return None
        child = page.get_child()
        return child if isinstance(child, EditorTab) else None

    def get_current_editor(self) -> AbstractEditor | None:
        tab = self.get_current_tab()
        return tab.get_editor() if tab is not None else None

    def save_current(self) -> None:
        tab = self.get_current_tab()
        if tab is None:
            return
        if tab.file_path is None:
            self.save_as_current(self._window)
        else:
            tab.save()
            self._notify_title_changed()

    def mark_current_saved(self) -> None:
        """Mark the current tab as unmodified (used for pipe-mode internal saves)."""
        tab = self.get_current_tab()
        if tab is not None:
            tab.mark_saved()
            self._notify_title_changed()

    def set_all_editors_editable(self, editable: bool) -> None:
        """Set the editable state of every open editor tab."""
        for index in range(self._tab_view.get_n_pages()):
            child = self._tab_view.get_nth_page(index).get_child()
            if isinstance(child, EditorTab):
                child.get_editor().set_editable(editable)

    def save_as_current(self, parent: Gtk.Window) -> None:
        dialog = Gtk.FileDialog.new()
        dialog.save(parent, None, self._on_save_as_response)

    def reload_current(self) -> None:
        tab = self.get_current_tab()
        if tab is None or tab.file_path is None:
            return
        try:
            file_size = os.path.getsize(tab.file_path)
        except OSError:
            file_size = 0
        if file_size > LARGE_FILE_SIZE_BYTES:
            self._show_file_too_large_dialog(tab.file_path, file_size)
            return
        tab.reload()

    def close_current_tab(self) -> None:
        page = self._tab_view.get_selected_page()
        if page is not None and self._tab_view.get_n_pages() > 1:
            self._tab_view.close_page(page)

    def next_tab(self) -> None:
        if self._tab_view.get_selected_page() is not None:
            self._tab_view.select_next_page()

    def prev_tab(self) -> None:
        if self._tab_view.get_selected_page() is not None:
            self._tab_view.select_previous_page()

    def _on_save_as_response(self, dialog: Gtk.FileDialog, result: object) -> None:
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        if gfile is None:
            return
        tab = self.get_current_tab()
        if tab is None:
            return
        tab.file_path = gfile.get_path()
        tab.save()
        page = self._tab_view.get_selected_page()
        if page is not None:
            page.set_title(tab.title)
        self._notify_title_changed()

    def _show_file_too_large_dialog(self, path: str, size: int) -> None:
        size_mb = size / (1024 * 1024)
        limit_mb = LARGE_FILE_SIZE_BYTES / (1024 * 1024)
        dialog = Adw.AlertDialog.new(
            "File Too Large to Open",
            f"\u201c{os.path.basename(path)}\u201d is {size_mb:.1f}\u202fMB, which "
            f"exceeds the {limit_mb:.0f}\u202fMB limit.\n\n"
            "Large files would cause slow syntax highlighting and unresponsive "
            "live preview rendering.",
        )
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.present(self._window)

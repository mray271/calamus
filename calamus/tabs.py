"""Tab abstractions and Adwaita-backed implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
import os

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from calamus.editor import AbstractEditor, MarkdownEditor
from calamus.preview import AbstractPreview, create_preview
from calamus.preferences import FileConfigProvider


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
    def reload(self) -> None:
        """Reload the tab contents from disk."""

    @abstractmethod
    def load_file(self, path: str) -> None:
        """Load file contents into the tab."""


@AbstractTab.register
class EditorTab(Gtk.Box):
    """Concrete editor tab implementation."""

    def __init__(self, file_path: str | None = None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._file_path = file_path
        self._modified = False
        self.search_bar = Gtk.SearchBar()
        self.search_entry = Gtk.SearchEntry()
        self.editor: MarkdownEditor = MarkdownEditor()
        self.preview: AbstractPreview = create_preview()
        self._build_ui()
        self.editor.configure_from_prefs(FileConfigProvider().load())
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

    def reload(self) -> None:
        if self._file_path is not None:
            self.load_file(self._file_path)

    def load_file(self, path: str) -> None:
        self._file_path = path
        try:
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()
        except OSError as error:
            content = f"Error loading file: {error}"
        self.editor.set_text(content)
        self.preview.update(content)
        self._modified = False

    def _build_ui(self) -> None:
        self.search_bar.set_child(self.search_entry)
        self.search_bar.connect_entry(self.search_entry)
        self.append(self.search_bar)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        self.append(paned)

        scroll_editor = Gtk.ScrolledWindow()
        scroll_editor.set_child(self.editor)
        paned.set_start_child(scroll_editor)

        scroll_preview = Gtk.ScrolledWindow()
        scroll_preview.set_child(self.preview.get_widget())
        paned.set_end_child(scroll_preview)

        self.editor.get_buffer().connect("changed", self._on_buffer_changed)

    def _on_buffer_changed(self, _buffer: object) -> None:
        self._modified = True
        self.preview.update(self.editor.get_text())


class AbstractTabManager(ABC):
    """Defines tab-management behavior."""

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


@AbstractTabManager.register
class AdwTabManager(Adw.TabView):
    """Adwaita TabView-based tab manager."""

    def __init__(self, window: Gtk.Window) -> None:
        super().__init__()
        self._window = window
        self.set_vexpand(True)
        self.new_tab()

    def new_tab(self, file_path: str | None = None) -> AbstractTab:
        tab = EditorTab(file_path)
        page = self.append(tab)
        page.set_title(tab.title)
        tab.editor.get_buffer().connect(
            "changed", lambda *_args: page.set_title(tab.title)
        )
        self.set_selected_page(page)
        return tab

    def open_file(self, path: str) -> None:
        for index in range(self.get_n_pages()):
            page = self.get_nth_page(index)
            child = page.get_child()
            if isinstance(child, EditorTab) and child.file_path == path:
                self.set_selected_page(page)
                return
        self.new_tab(path)

    def get_current_tab(self) -> AbstractTab | None:
        page = self.get_selected_page()
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

    def save_as_current(self, parent: Gtk.Window) -> None:
        dialog = Gtk.FileDialog.new()
        dialog.save(parent, None, self._on_save_as_response)

    def reload_current(self) -> None:
        tab = self.get_current_tab()
        if tab is not None:
            tab.reload()

    def close_current_tab(self) -> None:
        page = self.get_selected_page()
        if page is not None and self.get_n_pages() > 1:
            self.close_page(page)

    def next_tab(self) -> None:
        if self.get_selected_page() is not None:
            self.select_next_page()

    def prev_tab(self) -> None:
        if self.get_selected_page() is not None:
            self.select_previous_page()

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
        page = self.get_selected_page()
        if page is not None:
            page.set_title(tab.title)

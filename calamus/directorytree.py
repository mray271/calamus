"""Directory tree abstractions and GTK implementation."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk


class AbstractDirectoryPane(ABC):
    """Defines directory sidebar behavior."""

    @abstractmethod
    def load_directory(self, path: str) -> None:
        """Load a directory into the pane."""

    @abstractmethod
    def get_widget(self) -> Gtk.Widget:
        """Return the widget backing the pane."""

    @abstractmethod
    def connect_file_activated(self, callback: Callable[[str], None]) -> None:
        """Connect a file-activation callback."""


@AbstractDirectoryPane.register
class GtkDirectoryPane(Gtk.Box):
    """GTK TreeView-backed directory pane."""

    _MAX_TRAVERSAL_DEPTH = 32
    _MAX_TRAVERSAL_DIRECTORIES = 5000
    _MIN_FONT_SIZE_PT = 8.0
    _MAX_FONT_SIZE_PT = 36.0
    _DEFAULT_FONT_SIZE_PT = 11.0

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._callbacks: list[Callable[[str], None]] = []
        self._store = Gtk.TreeStore(str, str)
        self._tree = Gtk.TreeView(model=self._store)
        self._header_label: Gtk.Label | None = None
        self._renderer: Gtk.CellRendererText | None = None
        self._css_provider = Gtk.CssProvider()
        self._font_size_pt = self._DEFAULT_FONT_SIZE_PT
        self._visited_directories: set[object] = set()
        self._visited_directory_count = 0
        self._max_traversal_depth = self._MAX_TRAVERSAL_DEPTH
        self._max_traversal_directories = self._MAX_TRAVERSAL_DIRECTORIES
        self.set_size_request(200, -1)
        self.add_css_class("calamus-directory-pane")
        self._build_ui()

    def load_directory(self, path: str) -> None:
        self._store.clear()
        self._visited_directories.clear()
        self._visited_directory_count = 0
        self._populate(None, path)

    def get_widget(self) -> Gtk.Widget:
        return self

    def connect_file_activated(self, callback: Callable[[str], None]) -> None:
        self._callbacks.append(callback)

    def zoom_by(self, factor: float) -> None:
        if factor <= 0:
            return
        size = max(
            self._MIN_FONT_SIZE_PT,
            min(self._MAX_FONT_SIZE_PT, round(self._font_size_pt * factor, 1)),
        )
        self._apply_font_size(size)

    def reset_zoom(self) -> None:
        self._apply_font_size(self._DEFAULT_FONT_SIZE_PT)

    def _build_ui(self) -> None:
        label = Gtk.Label(label="Files")
        label.set_xalign(0)
        label.add_css_class("heading")
        self._header_label = label
        self.append(label)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        self.append(scroll)

        self._tree.set_headers_visible(False)
        renderer = Gtk.CellRendererText()
        self._renderer = renderer
        column = Gtk.TreeViewColumn("Name", renderer, text=0)
        self._tree.append_column(column)
        self._tree.connect("row-activated", self._on_row_activated)
        scroll.set_child(self._tree)
        self._apply_font_size(self._font_size_pt)

        self.load_directory(os.getcwd())

    def _apply_font_size(self, size_pt: float) -> None:
        self._font_size_pt = size_pt
        if self._renderer is not None:
            self._renderer.set_property("size-points", float(size_pt))
        self._css_provider.load_from_string(
            ".calamus-directory-pane label, "
            ".calamus-directory-pane treeview { "
            f"font-size: {self._font_size_pt}pt; }}"
        )
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _populate(self, parent_iter: object, path: str, depth: int = 0) -> None:
        if not self._enter_directory(path, depth):
            return
        try:
            entries = sorted(
                os.scandir(path),
                key=self._entry_sort_key,
            )
        except (PermissionError, OSError):
            return
        for entry in entries:
            if entry.name.startswith("."):
                continue
            tree_iter = self._store.append(parent_iter, [entry.name, entry.path])
            if self._safe_is_dir(entry):
                self._populate(tree_iter, entry.path, depth + 1)

    def _entry_sort_key(self, entry: os.DirEntry[str]) -> tuple[bool, str]:
        return (not self._safe_is_dir(entry), entry.name.lower())

    @staticmethod
    def _safe_is_dir(entry: os.DirEntry[str]) -> bool:
        try:
            return entry.is_dir(follow_symlinks=True)
        except OSError:
            return False

    def _enter_directory(self, path: str, depth: int) -> bool:
        if depth > self._max_traversal_depth:
            return False
        if self._visited_directory_count >= self._max_traversal_directories:
            return False
        identity = self._directory_identity(path)
        if identity in self._visited_directories:
            return False
        self._visited_directories.add(identity)
        self._visited_directory_count += 1
        return True

    @staticmethod
    def _directory_identity(path: str) -> object:
        try:
            stat_result = os.stat(path, follow_symlinks=True)
            return ("inode", stat_result.st_dev, stat_result.st_ino)
        except OSError:
            return ("realpath", os.path.realpath(path))

    def _on_row_activated(
        self,
        _tree: Gtk.TreeView,
        tree_path: Gtk.TreePath,
        _column: Gtk.TreeViewColumn,
    ) -> None:
        tree_iter = self._store.get_iter(tree_path)
        path = self._store.get_value(tree_iter, 1)
        if not path or os.path.isdir(path):
            return
        for callback in self._callbacks:
            callback(path)

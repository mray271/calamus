"""Directory tree abstractions and GTK implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
import os

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

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._callbacks: list[Callable[[str], None]] = []
        self._store = Gtk.TreeStore(str, str)
        self._tree = Gtk.TreeView(model=self._store)
        self.set_size_request(200, -1)
        self._build_ui()

    def load_directory(self, path: str) -> None:
        self._store.clear()
        self._populate(None, path)

    def get_widget(self) -> Gtk.Widget:
        return self

    def connect_file_activated(self, callback: Callable[[str], None]) -> None:
        self._callbacks.append(callback)

    def _build_ui(self) -> None:
        label = Gtk.Label(label="Files")
        label.set_xalign(0)
        label.add_css_class("heading")
        self.append(label)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        self.append(scroll)

        self._tree.set_headers_visible(False)
        column = Gtk.TreeViewColumn("Name", Gtk.CellRendererText(), text=0)
        self._tree.append_column(column)
        self._tree.connect("row-activated", self._on_row_activated)
        scroll.set_child(self._tree)

        self.load_directory(os.path.expanduser("~"))

    def _populate(self, parent_iter: object, path: str) -> None:
        try:
            entries = sorted(
                os.scandir(path),
                key=lambda entry: (not entry.is_dir(), entry.name.lower()),
            )
        except PermissionError:
            return
        for entry in entries:
            if entry.name.startswith("."):
                continue
            tree_iter = self._store.append(parent_iter, [entry.name, entry.path])
            if entry.is_dir():
                self._populate(tree_iter, entry.path)

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

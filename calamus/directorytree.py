"""Directory tree abstractions and GTK implementation."""

from __future__ import annotations

import os
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk


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

    @abstractmethod
    def load_parent_directory(self) -> None:
        """Load the parent directory when available."""

    @abstractmethod
    def load_home_directory(self) -> None:
        """Load the current user's home directory."""

    def zoom_by(self, factor: float) -> None:
        """Scale the pane font size by a factor. No-op by default."""

    def reset_zoom(self) -> None:
        """Reset pane zoom to default. No-op by default."""


class GtkDirectoryPane(AbstractDirectoryPane):
    """GTK TreeView-backed directory pane."""

    _MAX_TRAVERSAL_DEPTH = 32
    _MAX_TRAVERSAL_DIRECTORIES = 50000
    _NAME_COLUMN = 0
    _PATH_COLUMN = 1
    _IS_DIR_COLUMN = 2
    _IS_LOADED_COLUMN = 3
    _IS_LOADING_COLUMN = 4
    _NODE_ID_COLUMN = 5
    _MIN_FONT_SIZE_PT = 8.0
    _MAX_FONT_SIZE_PT = 36.0
    _DEFAULT_FONT_SIZE_PT = 11.0

    def __init__(self) -> None:
        super().__init__()
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._callbacks: list[Callable[[str], None]] = []
        self._store = Gtk.TreeStore(str, str, bool, bool, bool, int)
        self._tree = Gtk.TreeView(model=self._store)
        self._header_label: Gtk.Label | None = None
        self._renderer: Gtk.CellRendererText | None = None
        self._css_provider = Gtk.CssProvider()
        self._font_size_pt = self._DEFAULT_FONT_SIZE_PT
        self._visited_directory_count = 0
        self._max_traversal_depth = self._MAX_TRAVERSAL_DEPTH
        self._max_traversal_directories = self._MAX_TRAVERSAL_DIRECTORIES
        self._current_directory = os.getcwd()
        self._next_node_id = 1
        self._next_request_id = 1
        self._root_request_id = 0
        self._pending_requests: dict[int, int] = {}
        self._box.set_size_request(200, -1)
        self._box.add_css_class("calamus-directory-pane")
        self._build_ui()

    def load_directory(self, path: str) -> None:
        normalized_path = self._normalize_directory_path(path)
        if normalized_path is None:
            return
        self._current_directory = normalized_path
        if self._header_label is not None:
            self._header_label.set_tooltip_text(self._current_directory)
        self._store.clear()
        self._pending_requests.clear()
        self._visited_directory_count = 0
        if not self._enter_directory(self._current_directory, depth=0):
            self._append_status_row(
                None,
                "Directory traversal limit reached.",
            )
            return
        self._append_status_row(None, "Loading…")
        self._root_request_id += 1
        self._start_root_scan(self._root_request_id, self._current_directory)

    def get_widget(self) -> Gtk.Widget:
        return self._box

    def connect_file_activated(self, callback: Callable[[str], None]) -> None:
        self._callbacks.append(callback)

    def load_parent_directory(self) -> None:
        parent = os.path.dirname(self._current_directory)
        if parent == self._current_directory:
            return
        self.load_directory(parent)

    def load_home_directory(self) -> None:
        self.load_directory(os.path.expanduser("~"))

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
        self._box.append(label)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        self._box.append(scroll)

        self._tree.set_headers_visible(False)
        renderer = Gtk.CellRendererText()
        self._renderer = renderer
        column = Gtk.TreeViewColumn("Name", renderer, text=0)
        self._tree.append_column(column)
        self._tree.connect("row-activated", self._on_row_activated)
        self._tree.connect("row-expanded", self._on_row_expanded)
        self._tree.connect("row-collapsed", self._on_row_collapsed)

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
            self._box.get_display(),
            self._css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    @staticmethod
    def _entry_sort_key(entry: tuple[str, str, bool]) -> tuple[bool, str]:
        name, _path, is_dir = entry
        return (not is_dir, name.lower())

    @staticmethod
    def _normalize_directory_path(path: str) -> str | None:
        candidate = os.path.abspath(os.path.expanduser(path))
        if os.path.isfile(candidate):
            candidate = os.path.dirname(candidate)
        if not os.path.isdir(candidate):
            return None
        return candidate

    @staticmethod
    def _safe_is_dir(entry: os.DirEntry[str]) -> bool:
        try:
            return entry.is_dir(follow_symlinks=True)
        except OSError:
            return False

    def _scan_directory(
        self, path: str
    ) -> tuple[list[tuple[str, str, bool]], str | None]:
        try:
            with os.scandir(path) as iterator:
                entries: list[tuple[str, str, bool]] = []
                for entry in iterator:
                    if entry.name.startswith("."):
                        continue
                    entries.append((entry.name, entry.path, self._safe_is_dir(entry)))
            entries.sort(key=self._entry_sort_key)
            return entries, None
        except PermissionError:
            return [], "Permission denied."
        except OSError as exc:
            return [], exc.strerror or "Unable to read directory."

    def _start_root_scan(self, request_id: int, path: str) -> None:
        def _worker() -> None:
            entries, error = self._scan_directory(path)
            GLib.idle_add(self._on_root_scan_complete, request_id, path, entries, error)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_root_scan_complete(
        self,
        request_id: int,
        path: str,
        entries: list[tuple[str, str, bool]],
        error: str | None,
    ) -> bool:
        if request_id != self._root_request_id or path != self._current_directory:
            return False
        self._store.clear()
        if error is not None:
            self._append_status_row(None, error)
            return False
        for name, entry_path, is_dir in entries:
            self._append_entry(None, name, entry_path, is_dir)
        return False

    def _start_directory_scan(self, node_id: int, request_id: int, path: str) -> None:
        def _worker() -> None:
            entries, error = self._scan_directory(path)
            GLib.idle_add(
                self._on_directory_scan_complete,
                node_id,
                request_id,
                path,
                entries,
                error,
            )

        threading.Thread(target=_worker, daemon=True).start()

    def _enter_directory(self, path: str, depth: int) -> bool:
        if depth > self._max_traversal_depth:
            return False
        if self._visited_directory_count >= self._max_traversal_directories:
            return False
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
        path = self._store.get_value(tree_iter, self._PATH_COLUMN)
        is_dir = self._store.get_value(tree_iter, self._IS_DIR_COLUMN)
        if not path:
            return
        if is_dir:
            if self._tree.row_expanded(tree_path):
                self._tree.collapse_row(tree_path)
            else:
                self._tree.expand_row(tree_path, False)
            return
        for callback in self._callbacks:
            callback(path)

    def _on_row_expanded(
        self,
        _tree: Gtk.TreeView,
        tree_iter: Gtk.TreeIter,
        _tree_path: Gtk.TreePath,
    ) -> None:
        is_dir = self._store.get_value(tree_iter, self._IS_DIR_COLUMN)
        is_loaded = self._store.get_value(tree_iter, self._IS_LOADED_COLUMN)
        is_loading = self._store.get_value(tree_iter, self._IS_LOADING_COLUMN)
        if not is_dir or is_loaded or is_loading:
            return
        path = self._store.get_value(tree_iter, self._PATH_COLUMN)
        if not path:
            return
        depth = self._store.get_path(tree_iter).get_depth()
        if not self._enter_directory(path, depth):
            self._clear_children(tree_iter)
            self._append_status_row(tree_iter, "Directory traversal limit reached.")
            self._store.set_value(tree_iter, self._IS_LOADED_COLUMN, True)
            self._store.set_value(tree_iter, self._IS_LOADING_COLUMN, False)
            return
        if self._is_ancestor_cycle(tree_iter, path):
            self._clear_children(tree_iter)
            self._append_status_row(tree_iter, "Cyclic symbolic link detected.")
            self._store.set_value(tree_iter, self._IS_LOADED_COLUMN, True)
            self._store.set_value(tree_iter, self._IS_LOADING_COLUMN, False)
            return

        self._clear_children(tree_iter)
        self._append_status_row(tree_iter, "Loading…")
        self._store.set_value(tree_iter, self._IS_LOADING_COLUMN, True)
        node_id = self._store.get_value(tree_iter, self._NODE_ID_COLUMN)
        request_id = self._next_request_id
        self._next_request_id += 1
        self._pending_requests[node_id] = request_id
        self._start_directory_scan(node_id, request_id, path)

    def _on_directory_scan_complete(
        self,
        node_id: int,
        request_id: int,
        path: str,
        entries: list[tuple[str, str, bool]],
        error: str | None,
    ) -> bool:
        pending_request_id = self._pending_requests.get(node_id)
        if pending_request_id != request_id:
            return False
        self._pending_requests.pop(node_id, None)

        tree_iter = self._find_iter_by_node_id(node_id)
        if tree_iter is None:
            return False
        current_path = self._store.get_value(tree_iter, self._PATH_COLUMN)
        if current_path != path:
            return False

        self._clear_children(tree_iter)
        if error is not None:
            self._append_status_row(tree_iter, error)
            self._store.set_value(tree_iter, self._IS_LOADED_COLUMN, True)
            self._store.set_value(tree_iter, self._IS_LOADING_COLUMN, False)
            return False

        for name, entry_path, is_dir in entries:
            self._append_entry(tree_iter, name, entry_path, is_dir)

        self._store.set_value(tree_iter, self._IS_LOADED_COLUMN, True)
        self._store.set_value(tree_iter, self._IS_LOADING_COLUMN, False)
        if self._store.iter_has_child(tree_iter):
            tree_path = self._store.get_path(tree_iter)
            self._tree.expand_row(tree_path, False)
        return False

    def _on_row_collapsed(
        self,
        _tree: Gtk.TreeView,
        tree_iter: Gtk.TreeIter,
        _tree_path: Gtk.TreePath,
    ) -> None:
        if not self._store.get_value(tree_iter, self._IS_DIR_COLUMN):
            return
        node_id = self._store.get_value(tree_iter, self._NODE_ID_COLUMN)
        self._pending_requests.pop(node_id, None)
        self._store.set_value(tree_iter, self._IS_LOADING_COLUMN, False)
        self._store.set_value(tree_iter, self._IS_LOADED_COLUMN, False)
        self._clear_children(tree_iter)
        self._append_placeholder_child(tree_iter)

    def _clear_children(self, parent_iter: Gtk.TreeIter) -> None:
        child_iter = self._store.iter_children(parent_iter)
        while child_iter is not None:
            has_next = self._store.remove(child_iter)
            if not has_next:
                child_iter = None

    def _append_entry(
        self,
        parent_iter: Gtk.TreeIter | None,
        name: str,
        path: str,
        is_dir: bool,
    ) -> Gtk.TreeIter:
        tree_iter = self._store.append(
            parent_iter,
            [
                name,
                path,
                is_dir,
                not is_dir,
                False,
                self._next_node_id,
            ],
        )
        self._next_node_id += 1
        if is_dir:
            self._append_placeholder_child(tree_iter)
        return tree_iter

    def _append_status_row(
        self, parent_iter: Gtk.TreeIter | None, message: str
    ) -> None:
        self._store.append(parent_iter, [message, "", False, True, False, 0])

    def _append_placeholder_child(self, parent_iter: Gtk.TreeIter) -> None:
        self._store.append(parent_iter, ["", "", False, True, False, 0])

    def _find_iter_by_node_id(self, node_id: int) -> Gtk.TreeIter | None:
        found_iter: Gtk.TreeIter | None = None

        def _visitor(
            model: Gtk.TreeStore,
            tree_path: Gtk.TreePath,
            tree_iter: Gtk.TreeIter,
            _data: object,
        ) -> bool:
            nonlocal found_iter
            if model.get_value(tree_iter, self._NODE_ID_COLUMN) == node_id:
                found_iter = model.get_iter(tree_path)
                return True
            return False

        self._store.foreach(_visitor, None)
        return found_iter

    def _is_ancestor_cycle(self, tree_iter: Gtk.TreeIter, path: str) -> bool:
        identity = self._directory_identity(path)
        parent_iter = self._store.iter_parent(tree_iter)
        while parent_iter is not None:
            parent_path = self._store.get_value(parent_iter, self._PATH_COLUMN)
            if parent_path and self._directory_identity(parent_path) == identity:
                return True
            parent_iter = self._store.iter_parent(parent_iter)
        return False

"""Tests for directory tree safety and navigation helpers."""

from __future__ import annotations

import errno
import os

from calamus.directorytree import GtkDirectoryPane


class _FakeEntry:
    def __init__(
        self,
        name: str,
        path: str,
        *,
        is_dir_with_follow: bool = False,
        error: OSError | None = None,
    ) -> None:
        self.name = name
        self.path = path
        self._is_dir_with_follow = is_dir_with_follow
        self._error = error

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        assert follow_symlinks is True
        if self._error is not None:
            raise self._error
        return self._is_dir_with_follow


class _FakeScandir:
    def __init__(self, entries: list[_FakeEntry]) -> None:
        self._entries = entries

    def __enter__(self) -> _FakeScandir:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def __iter__(self):
        return iter(self._entries)


class _TestPane:
    load_parent_directory = GtkDirectoryPane.load_parent_directory
    load_home_directory = GtkDirectoryPane.load_home_directory
    _scan_directory = GtkDirectoryPane._scan_directory
    _entry_sort_key = staticmethod(GtkDirectoryPane._entry_sort_key)
    _safe_is_dir = staticmethod(GtkDirectoryPane._safe_is_dir)
    _enter_directory = GtkDirectoryPane._enter_directory
    _PATH_COLUMN = GtkDirectoryPane._PATH_COLUMN
    _IS_DIR_COLUMN = GtkDirectoryPane._IS_DIR_COLUMN

    def __init__(self) -> None:
        self._current_directory = "/tmp"
        self._visited_directory_count = 0
        self._max_traversal_depth = GtkDirectoryPane._MAX_TRAVERSAL_DEPTH
        self._max_traversal_directories = GtkDirectoryPane._MAX_TRAVERSAL_DIRECTORIES


class _FakeStore:
    def __init__(self, rows: dict[object, dict[int, object]]) -> None:
        self._rows = rows

    def get_iter(self, tree_path: object) -> object:
        return tree_path

    def get_value(self, tree_iter: object, column: int) -> object:
        return self._rows[tree_iter][column]


class _FakeTree:
    def __init__(self, expanded_paths: set[object] | None = None) -> None:
        self.expanded_paths = expanded_paths or set()
        self.expanded_calls: list[object] = []
        self.collapsed_calls: list[object] = []

    def row_expanded(self, tree_path: object) -> bool:
        return tree_path in self.expanded_paths

    def expand_row(self, tree_path: object, _open_all: bool) -> None:
        self.expanded_calls.append(tree_path)
        self.expanded_paths.add(tree_path)

    def collapse_row(self, tree_path: object) -> None:
        self.collapsed_calls.append(tree_path)
        self.expanded_paths.discard(tree_path)


def test_scan_directory_tolerates_oserror_from_is_dir(monkeypatch):
    pane = _TestPane()
    entries = [
        _FakeEntry(
            "loop",
            "/tmp/loop",
            error=OSError(errno.ELOOP, "Too many levels of symbolic links"),
        ),
        _FakeEntry("notes.md", "/tmp/notes.md", is_dir_with_follow=False),
    ]
    monkeypatch.setattr(os, "scandir", lambda _path: _FakeScandir(entries))

    scanned, error = pane._scan_directory("/tmp")

    assert error is None
    assert scanned == [
        ("loop", "/tmp/loop", False),
        ("notes.md", "/tmp/notes.md", False),
    ]


def test_scan_directory_reports_permission_denied(monkeypatch):
    pane = _TestPane()

    def raise_permission(_path: str):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(os, "scandir", raise_permission)

    scanned, error = pane._scan_directory("/tmp")

    assert scanned == []
    assert error == "Permission denied."


def test_scan_directory_sorts_directories_before_files(monkeypatch):
    pane = _TestPane()
    entries = [
        _FakeEntry("zeta.txt", "/tmp/zeta.txt", is_dir_with_follow=False),
        _FakeEntry("beta", "/tmp/beta", is_dir_with_follow=True),
        _FakeEntry("Alpha", "/tmp/Alpha", is_dir_with_follow=True),
    ]
    monkeypatch.setattr(os, "scandir", lambda _path: _FakeScandir(entries))

    scanned, error = pane._scan_directory("/tmp")

    assert error is None
    assert scanned == [
        ("Alpha", "/tmp/Alpha", True),
        ("beta", "/tmp/beta", True),
        ("zeta.txt", "/tmp/zeta.txt", False),
    ]


def test_enter_directory_stops_after_directory_budget():
    pane = _TestPane()
    pane._max_traversal_directories = 2

    assert pane._enter_directory("/tmp", depth=0) is True
    assert pane._enter_directory("/tmp/a", depth=1) is True
    assert pane._enter_directory("/tmp/a/b", depth=2) is False


def test_load_parent_directory_navigates_up_one_level():
    pane = _TestPane()
    pane._current_directory = "/tmp/a/b"
    loaded_paths: list[str] = []
    pane.load_directory = loaded_paths.append  # type: ignore[method-assign]

    pane.load_parent_directory()

    assert loaded_paths == ["/tmp/a"]


def test_load_parent_directory_stops_at_root():
    pane = _TestPane()
    pane._current_directory = "/"
    loaded_paths: list[str] = []
    pane.load_directory = loaded_paths.append  # type: ignore[method-assign]

    pane.load_parent_directory()

    assert loaded_paths == []


def test_load_home_directory_uses_expanduser(monkeypatch):
    pane = _TestPane()
    loaded_paths: list[str] = []
    pane.load_directory = loaded_paths.append  # type: ignore[method-assign]
    monkeypatch.setattr(os.path, "expanduser", lambda value: "/home/tester")

    pane.load_home_directory()

    assert loaded_paths == ["/home/tester"]


def test_row_activated_expands_directory_without_firing_file_callbacks():
    tree_path = object()
    pane = _TestPane()
    pane._store = _FakeStore(
        {
            tree_path: {
                GtkDirectoryPane._PATH_COLUMN: "/tmp/project",
                GtkDirectoryPane._IS_DIR_COLUMN: True,
            }
        }
    )
    pane._tree = _FakeTree()
    callbacks: list[str] = []
    pane._callbacks = callbacks

    GtkDirectoryPane._on_row_activated(pane, pane._tree, tree_path, None)

    assert pane._tree.expanded_calls == [tree_path]
    assert pane._tree.collapsed_calls == []
    assert callbacks == []


def test_row_activated_collapses_expanded_directory():
    tree_path = object()
    pane = _TestPane()
    pane._store = _FakeStore(
        {
            tree_path: {
                GtkDirectoryPane._PATH_COLUMN: "/tmp/project",
                GtkDirectoryPane._IS_DIR_COLUMN: True,
            }
        }
    )
    pane._tree = _FakeTree(expanded_paths={tree_path})
    callbacks: list[str] = []
    pane._callbacks = callbacks

    GtkDirectoryPane._on_row_activated(pane, pane._tree, tree_path, None)

    assert pane._tree.expanded_calls == []
    assert pane._tree.collapsed_calls == [tree_path]
    assert callbacks == []


def test_row_activated_opens_files():
    tree_path = object()
    pane = _TestPane()
    pane._store = _FakeStore(
        {
            tree_path: {
                GtkDirectoryPane._PATH_COLUMN: "/tmp/project/notes.md",
                GtkDirectoryPane._IS_DIR_COLUMN: False,
            }
        }
    )
    pane._tree = _FakeTree()
    callbacks: list[str] = []
    pane._callbacks = [callbacks.append]

    GtkDirectoryPane._on_row_activated(pane, pane._tree, tree_path, None)

    assert callbacks == ["/tmp/project/notes.md"]

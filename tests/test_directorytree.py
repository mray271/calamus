"""Tests for directory tree handling of problematic symlink entries."""

from __future__ import annotations

import errno
import os
import types

from calamus.directorytree import GtkDirectoryPane


class _FakeStore:
    def __init__(self) -> None:
        self.rows: list[tuple[object, list[str]]] = []

    def append(self, parent_iter: object, values: list[str]) -> object:
        self.rows.append((parent_iter, values))
        return object()


class _FakeEntry:
    def __init__(
        self,
        name: str,
        path: str,
        *,
        is_dir_without_follow: bool = False,
        is_dir_with_follow: bool | None = None,
        error: OSError | None = None,
    ) -> None:
        self.name = name
        self.path = path
        self._is_dir_without_follow = is_dir_without_follow
        self._is_dir_with_follow = (
            is_dir_with_follow
            if is_dir_with_follow is not None
            else is_dir_without_follow
        )
        self._error = error

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        if self._error is not None:
            raise self._error
        if follow_symlinks:
            return self._is_dir_with_follow
        return self._is_dir_without_follow


class _TestPane:
    _populate = GtkDirectoryPane._populate
    _entry_sort_key = GtkDirectoryPane._entry_sort_key
    _safe_is_dir = staticmethod(GtkDirectoryPane._safe_is_dir)
    _enter_directory = GtkDirectoryPane._enter_directory
    _directory_identity = staticmethod(GtkDirectoryPane._directory_identity)

    def __init__(self) -> None:
        self._store = _FakeStore()
        self._visited_directories: set[object] = set()
        self._visited_directory_count = 0
        self._max_traversal_depth = GtkDirectoryPane._MAX_TRAVERSAL_DEPTH
        self._max_traversal_directories = GtkDirectoryPane._MAX_TRAVERSAL_DIRECTORIES


def test_populate_tolerates_oserror_from_is_dir(monkeypatch):
    pane = _TestPane()
    entries = [
        _FakeEntry(
            "loop",
            "/tmp/loop",
            error=OSError(errno.ELOOP, "Too many levels of symbolic links"),
        ),
        _FakeEntry("notes.md", "/tmp/notes.md"),
    ]
    monkeypatch.setattr(os, "scandir", lambda _path: entries)

    pane._populate(None, "/tmp")

    names = [values[0] for _parent, values in pane._store.rows]
    assert names == ["loop", "notes.md"]


def test_populate_follows_symlinked_directory_and_stops_on_cycle(monkeypatch):
    pane = _TestPane()
    calls: list[str] = []
    entries_by_path = {
        "/tmp": [
            _FakeEntry(
                "linked-dir",
                "/tmp/linked-dir",
                is_dir_without_follow=False,
                is_dir_with_follow=True,
            )
        ],
        "/tmp/linked-dir": [
            _FakeEntry(
                "back-to-root",
                "/tmp",
                is_dir_without_follow=False,
                is_dir_with_follow=True,
            )
        ],
    }
    inode_by_path = {
        "/tmp": (1, 100),
        "/tmp/linked-dir": (1, 200),
    }

    def fake_scandir(path: str):
        calls.append(path)
        return entries_by_path[path]

    def fake_stat(path: str, *, follow_symlinks: bool = True):
        assert follow_symlinks is True
        dev, ino = inode_by_path[path]
        return types.SimpleNamespace(st_dev=dev, st_ino=ino)

    monkeypatch.setattr(os, "scandir", fake_scandir)
    monkeypatch.setattr(os, "stat", fake_stat)

    pane._populate(None, "/tmp")

    assert calls == ["/tmp", "/tmp/linked-dir"]


def test_populate_stops_after_directory_budget(monkeypatch):
    pane = _TestPane()
    pane._max_traversal_directories = 2
    calls: list[str] = []
    entries_by_path = {
        "/tmp": [
            _FakeEntry("a", "/tmp/a", is_dir_with_follow=True),
        ],
        "/tmp/a": [
            _FakeEntry("b", "/tmp/a/b", is_dir_with_follow=True),
        ],
        "/tmp/a/b": [],
    }
    inode_by_path = {
        "/tmp": (1, 100),
        "/tmp/a": (1, 101),
        "/tmp/a/b": (1, 102),
    }

    def fake_scandir(path: str):
        calls.append(path)
        return entries_by_path[path]

    def fake_stat(path: str, *, follow_symlinks: bool = True):
        assert follow_symlinks is True
        dev, ino = inode_by_path[path]
        return types.SimpleNamespace(st_dev=dev, st_ino=ino)

    monkeypatch.setattr(os, "scandir", fake_scandir)
    monkeypatch.setattr(os, "stat", fake_stat)

    pane._populate(None, "/tmp")

    assert calls == ["/tmp", "/tmp/a"]

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

    def __init__(self) -> None:
        self._current_directory = "/tmp"
        self._visited_directory_count = 0
        self._max_traversal_depth = GtkDirectoryPane._MAX_TRAVERSAL_DEPTH
        self._max_traversal_directories = GtkDirectoryPane._MAX_TRAVERSAL_DIRECTORIES


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

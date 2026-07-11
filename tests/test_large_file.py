"""Tests for large-file rejection in EditorTab and AdwTabManager."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from calamus.tabs import LARGE_FILE_SIZE_BYTES, FileTooLargeError

# ---------------------------------------------------------------------------
# FileTooLargeError
# ---------------------------------------------------------------------------


def test_file_too_large_error_message():
    err = FileTooLargeError("/tmp/huge.md", 21 * 1024 * 1024, LARGE_FILE_SIZE_BYTES)
    assert "huge.md" in str(err)
    assert "21.0 MB" in str(err)


def test_file_too_large_error_attributes():
    size = 25 * 1024 * 1024
    err = FileTooLargeError("/docs/huge.md", size, LARGE_FILE_SIZE_BYTES)
    assert err.path == "/docs/huge.md"
    assert err.size == size
    assert err.limit == LARGE_FILE_SIZE_BYTES


# ---------------------------------------------------------------------------
# EditorTab.load_file — size gate (no GTK required, mocked)
# ---------------------------------------------------------------------------


class TestEditorTabLargeFileSafetyNet:
    """
    EditorTab.load_file() must raise FileTooLargeError for oversized files
    without ever opening them.
    """

    def _make_mock_tab(self):
        """Return an EditorTab-like object with load_file bound but GTK faked."""
        from calamus.tabs import EditorTab, LARGE_FILE_SIZE_BYTES

        tab = EditorTab.__new__(EditorTab)
        tab._file_path = None
        tab._modified = False
        tab.editor = MagicMock()
        tab.preview = MagicMock()
        return tab

    def test_load_file_raises_for_oversized_file(self, tmp_path):
        from calamus.tabs import EditorTab

        tab = self._make_mock_tab()
        large_file = tmp_path / "large.md"
        large_file.write_bytes(b"x" * 100)  # real file; stat will work

        oversized = LARGE_FILE_SIZE_BYTES + 1
        with patch("os.path.getsize", return_value=oversized):
            with pytest.raises(FileTooLargeError) as exc_info:
                EditorTab.load_file(tab, str(large_file))

        assert exc_info.value.size == oversized
        assert exc_info.value.limit == LARGE_FILE_SIZE_BYTES
        # Must not have read the file or set text
        tab.editor.set_text.assert_not_called()

    def test_load_file_succeeds_for_file_at_limit(self, tmp_path):
        from calamus.tabs import EditorTab

        tab = self._make_mock_tab()
        normal_file = tmp_path / "normal.md"
        normal_file.write_text("# Hello\n", encoding="utf-8")

        with patch("os.path.getsize", return_value=LARGE_FILE_SIZE_BYTES):
            EditorTab.load_file(tab, str(normal_file))

        tab.editor.set_text.assert_called_once()

    def test_load_file_succeeds_for_small_file(self, tmp_path):
        from calamus.tabs import EditorTab

        tab = self._make_mock_tab()
        small_file = tmp_path / "small.md"
        small_file.write_text("# Hi\n", encoding="utf-8")

        EditorTab.load_file(tab, str(small_file))

        tab.editor.set_text.assert_called_once_with("# Hi\n")

    def test_load_file_never_opens_oversized_file(self, tmp_path):
        from calamus.tabs import EditorTab

        tab = self._make_mock_tab()
        large_file = tmp_path / "huge.md"
        large_file.write_bytes(b"x" * 50)

        with patch("os.path.getsize", return_value=LARGE_FILE_SIZE_BYTES + 1):
            with patch("builtins.open") as mock_open:
                with pytest.raises(FileTooLargeError):
                    EditorTab.load_file(tab, str(large_file))
        mock_open.assert_not_called()


# ---------------------------------------------------------------------------
# AdwTabManager.open_file — size gate (window and GTK faked)
# ---------------------------------------------------------------------------


class TestAdwTabManagerLargeFileGate:
    """
    AdwTabManager.open_file() must refuse oversized files without creating a tab.
    """

    def _make_mock_manager(self):
        from calamus.tabs import AdwTabManager

        mgr = object.__new__(AdwTabManager)
        mgr._window = MagicMock()
        mgr._tab_view = MagicMock()
        mgr._tab_view.get_n_pages.return_value = 0
        return mgr

    def test_open_file_shows_dialog_for_oversized_file(self, tmp_path):
        from calamus.tabs import AdwTabManager

        mgr = self._make_mock_manager()
        path = str(tmp_path / "huge.md")

        oversized = LARGE_FILE_SIZE_BYTES + 1
        with patch("os.path.getsize", return_value=oversized):
            with patch.object(AdwTabManager, "_show_file_too_large_dialog") as mock_dlg:
                with patch.object(AdwTabManager, "new_tab") as mock_new_tab:
                    AdwTabManager.open_file(mgr, path)

        mock_dlg.assert_called_once_with(path, oversized)
        mock_new_tab.assert_not_called()

    def test_open_file_proceeds_for_normal_file(self, tmp_path):
        from calamus.tabs import AdwTabManager

        mgr = self._make_mock_manager()
        path = str(tmp_path / "normal.md")

        with patch("os.path.getsize", return_value=1024):
            with patch.object(AdwTabManager, "_show_file_too_large_dialog") as mock_dlg:
                with patch.object(AdwTabManager, "new_tab") as mock_new_tab:
                    AdwTabManager.open_file(mgr, path)

        mock_dlg.assert_not_called()
        mock_new_tab.assert_called_once_with(path)


# ---------------------------------------------------------------------------
# AdwTabManager.reload_current — size gate
# ---------------------------------------------------------------------------


class TestAdwTabManagerReloadLargeFileGate:
    def _make_mock_manager(self, file_path):
        from calamus.tabs import AdwTabManager

        mgr = object.__new__(AdwTabManager)
        mgr._window = MagicMock()
        mgr._tab_view = MagicMock()
        mock_tab = MagicMock()
        mock_tab.file_path = file_path
        mgr.get_current_tab = MagicMock(return_value=mock_tab)
        return mgr, mock_tab

    def test_reload_blocked_for_oversized_file(self, tmp_path):
        from calamus.tabs import AdwTabManager

        path = str(tmp_path / "huge.md")
        mgr, mock_tab = self._make_mock_manager(path)

        with patch("os.path.getsize", return_value=LARGE_FILE_SIZE_BYTES + 1):
            with patch.object(AdwTabManager, "_show_file_too_large_dialog") as mock_dlg:
                AdwTabManager.reload_current(mgr)

        mock_dlg.assert_called_once()
        mock_tab.reload.assert_not_called()

    def test_reload_proceeds_for_normal_file(self, tmp_path):
        from calamus.tabs import AdwTabManager

        path = str(tmp_path / "small.md")
        mgr, mock_tab = self._make_mock_manager(path)

        with patch("os.path.getsize", return_value=512):
            with patch.object(AdwTabManager, "_show_file_too_large_dialog") as mock_dlg:
                AdwTabManager.reload_current(mgr)

        mock_dlg.assert_not_called()
        mock_tab.reload.assert_called_once()


# ---------------------------------------------------------------------------
# LARGE_FILE_SIZE_BYTES constant sanity check
# ---------------------------------------------------------------------------


def test_large_file_limit_is_20mb():
    assert LARGE_FILE_SIZE_BYTES == 20 * 1024 * 1024

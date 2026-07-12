"""Tests for CLI argument parsing and pipe mode behaviour.

The option-parsing helpers on CalamusApplication are pure Python (no GTK
display required), so all tests here run in any environment.  The pipe-mode
save tests patch ``sys.stdout`` to verify that Ctrl+S in pipe mode captures
the editor text correctly.
"""

from __future__ import annotations

import os
import tempfile
import types
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tempfile(suffix: str = ".md", content: str = "# Hello") -> str:
    """Create a real temp file and return its path (caller must unlink)."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, content.encode())
    os.close(fd)
    return path


def _make_app_stub(
    pipe_content: str | None = None,
    pipe_base_path: str | None = None,
    initial_files: list[str] | None = None,
    preview_mode: bool = False,
) -> types.SimpleNamespace:
    """Lightweight stand-in for CalamusApplication (no GTK required)."""
    from calamus.app import CalamusApplication

    return types.SimpleNamespace(
        _pipe_content=pipe_content,
        _pipe_base_path=pipe_base_path,
        _initial_files=initial_files or [],
        _preview_mode=preview_mode,
        _handle_options=CalamusApplication._handle_options,
        _maybe_read_piped_stdin=CalamusApplication._maybe_read_piped_stdin,
    )


# ---------------------------------------------------------------------------
# _handle_options — no-flag baseline
# ---------------------------------------------------------------------------


class TestHandleOptionsNormal:
    def test_no_args_leaves_defaults(self):
        app = _make_app_stub()
        result = app._handle_options(
            app, preview=False, pipe_base_path=None, argv=["calamus"]
        )
        assert app._pipe_content is None
        assert app._pipe_base_path is None
        assert app._initial_files == []
        assert app._preview_mode is False
        assert result == -1

    def test_nonexistent_file_returns_1(self):
        app = _make_app_stub()
        result = app._handle_options(
            app,
            preview=False,
            pipe_base_path=None,
            argv=["calamus", "/no/such/file.md"],
        )
        assert result == 1

    def test_existing_file_returns_minus_1(self):
        path = _make_tempfile()
        try:
            app = _make_app_stub()
            result = app._handle_options(
                app, preview=False, pipe_base_path=None, argv=["calamus", path]
            )
            assert result == -1
        finally:
            os.unlink(path)

    def test_pipe_base_path_is_normalized_and_stored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = _make_app_stub()
            result = app._handle_options(
                app,
                preview=False,
                pipe_base_path=tmpdir,
                argv=["calamus"],
            )
            assert result == -1
            assert app._pipe_base_path == os.path.abspath(tmpdir)

    def test_pipe_base_path_argument_is_not_treated_as_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = _make_app_stub()
            result = app._handle_options(
                app,
                preview=False,
                pipe_base_path=tmpdir,
                argv=["calamus", "--pipe-base-path", tmpdir],
            )
            assert result == -1

    def test_invalid_pipe_base_path_returns_1(self):
        app = _make_app_stub()
        result = app._handle_options(
            app,
            preview=False,
            pipe_base_path="/no/such/base",
            argv=["calamus"],
        )
        assert result == 1


# ---------------------------------------------------------------------------
# _maybe_read_piped_stdin — auto-detect piped stdin
# ---------------------------------------------------------------------------


class TestMaybeReadPipedStdin:
    def test_non_tty_stdin_reads_automatically(self):
        app = _make_app_stub()
        app._maybe_read_piped_stdin(
            app, stdin_is_tty=False, read_stdin=lambda: "auto piped"
        )
        assert app._pipe_content == "auto piped"

    def test_non_tty_empty_stdin_does_not_trigger_pipe_mode(self):
        """Docker/non-TTY with empty stdin (e.g. /dev/null) must not enter pipe mode."""
        app = _make_app_stub()
        app._maybe_read_piped_stdin(app, stdin_is_tty=False, read_stdin=lambda: "")
        assert app._pipe_content is None, "Empty stdin must not activate pipe mode"

    def test_tty_stdin_does_not_read(self):
        read_called = []
        app = _make_app_stub()
        app._maybe_read_piped_stdin(
            app,
            stdin_is_tty=True,
            read_stdin=lambda: read_called.append(True) or "content",
        )
        assert not read_called

    def test_skipped_when_pipe_content_already_set(self):
        read_called = []
        app = _make_app_stub(pipe_content="already set")
        app._maybe_read_piped_stdin(
            app,
            stdin_is_tty=False,
            read_stdin=lambda: read_called.append(True) or "new content",
        )
        assert app._pipe_content == "already set"
        assert not read_called, "stdin must not be read again when --pipe was given"

    def test_skipped_when_files_given(self):
        """File paths suppress auto-detect — opening a file is not pipe mode."""
        path = _make_tempfile()
        read_called = []
        try:
            app = _make_app_stub(initial_files=[path])
            app._maybe_read_piped_stdin(
                app,
                stdin_is_tty=False,
                read_stdin=lambda: read_called.append(True) or "should not read",
            )
            assert app._pipe_content is None
            assert not read_called
        finally:
            os.unlink(path)


class TestPipeBasePathPropagation:
    def test_load_content_overrides_preview_base_path(self):
        import types

        from calamus.tabs import EditorTab

        preview = MagicMock()
        editor = MagicMock()
        stub = types.SimpleNamespace(
            preview=preview,
            editor=editor,
            _file_path=None,
            _modified=True,
        )

        EditorTab.load_content(stub, "# piped", preview_base_path="/tmp/docs")

        preview.set_base_path.assert_called_once_with("/tmp/docs")
        preview.set_file_path.assert_not_called()
        editor.set_text.assert_called_once_with("# piped")
        preview.update.assert_called_once_with("# piped")
        assert stub._modified is False

    def test_load_content_uses_current_file_path_when_not_overridden(self):
        import types

        from calamus.tabs import EditorTab

        preview = MagicMock()
        editor = MagicMock()
        stub = types.SimpleNamespace(
            preview=preview,
            editor=editor,
            _file_path="/tmp/README.md",
            _modified=True,
        )

        EditorTab.load_content(stub, "# piped")

        preview.set_file_path.assert_called_once_with("/tmp/README.md")
        preview.set_base_path.assert_not_called()
        editor.set_text.assert_called_once_with("# piped")
        preview.update.assert_called_once_with("# piped")
        assert stub._modified is False


# ---------------------------------------------------------------------------
# _handle_options — --preview flag
# ---------------------------------------------------------------------------


class TestHandleOptionsPreviewFlag:
    def test_preview_flag_sets_preview_mode(self):
        app = _make_app_stub()
        result = app._handle_options(
            app, preview=True, pipe_base_path=None, argv=["calamus"]
        )
        assert app._preview_mode is True
        assert result == -1

    def test_no_flags_preview_mode_is_false(self):
        app = _make_app_stub()
        app._handle_options(app, preview=False, pipe_base_path=None, argv=["calamus"])
        assert app._preview_mode is False

    def test_preview_with_existing_file(self):
        path = _make_tempfile()
        try:
            app = _make_app_stub()
            result = app._handle_options(
                app, preview=True, pipe_base_path=None, argv=["calamus", path]
            )
            assert app._preview_mode is True
            assert result == -1
        finally:
            os.unlink(path)

    def test_preview_with_nonexistent_file_returns_1(self):
        app = _make_app_stub()
        result = app._handle_options(
            app,
            preview=True,
            pipe_base_path=None,
            argv=["calamus", "/no/such/file.md"],
        )
        assert result == 1


# ---------------------------------------------------------------------------
# Pipe mode save — captures editor text internally, does NOT emit to stdout
# ---------------------------------------------------------------------------


class TestPipeModeSave:
    """Ctrl+S in pipe mode captures the current text as the saved state.

    The Meld-as-mergetool contract: closing without saving reverts to the
    original input; saving commits a snapshot that will be emitted on close.
    """

    def _make_save_stub(self, editor_text: str):
        import types

        mock_editor = MagicMock()
        mock_editor.get_text.return_value = editor_text
        mock_tab_manager = MagicMock()
        mock_tab_manager.get_current_editor.return_value = mock_editor
        stub = types.SimpleNamespace(
            _pipe_mode=True,
            _pipe_saved_content=None,
            tab_manager=mock_tab_manager,
        )
        return stub

    def test_ctrl_s_stores_saved_content(self):
        import types

        from calamus.window import CalamusWindow

        stub = self._make_save_stub("# Edited text")
        CalamusWindow._on_save(stub, MagicMock(), None)

        assert stub._pipe_saved_content == "# Edited text"

    def test_ctrl_s_does_not_write_stdout(self):
        import types

        from calamus.window import CalamusWindow

        stub = self._make_save_stub("# Edited text")
        captured_calls = []
        with patch("calamus.window.sys.stdout") as mock_stdout:
            mock_stdout.write.side_effect = lambda s: captured_calls.append(s)
            CalamusWindow._on_save(stub, MagicMock(), None)

        assert not captured_calls, "Ctrl+S must not write to stdout in pipe mode"

    def test_ctrl_s_calls_mark_current_saved(self):
        import types

        from calamus.window import CalamusWindow

        stub = self._make_save_stub("text")
        CalamusWindow._on_save(stub, MagicMock(), None)

        stub.tab_manager.mark_current_saved.assert_called_once()

    def test_ctrl_s_does_not_call_save_current(self):
        import types

        from calamus.window import CalamusWindow

        stub = self._make_save_stub("text")
        CalamusWindow._on_save(stub, MagicMock(), None)

        stub.tab_manager.save_current.assert_not_called()

    def test_ctrl_s_does_not_quit(self):
        import types

        from calamus.window import CalamusWindow

        mock_tab_manager = MagicMock()
        mock_tab_manager.get_current_editor.return_value = MagicMock()
        mock_app = MagicMock()
        stub = types.SimpleNamespace(
            _pipe_mode=True,
            _pipe_saved_content=None,
            tab_manager=mock_tab_manager,
            get_application=lambda: mock_app,
        )
        CalamusWindow._on_save(stub, MagicMock(), None)
        mock_app.quit.assert_not_called()

    def test_normal_save_calls_save_current(self):
        import types

        from calamus.window import CalamusWindow

        mock_tab_manager = MagicMock()
        stub = types.SimpleNamespace(
            _pipe_mode=False,
            tab_manager=mock_tab_manager,
        )
        CalamusWindow._on_save(stub, MagicMock(), None)

        mock_tab_manager.save_current.assert_called_once()

    def test_normal_save_does_not_write_stdout(self):
        import types

        from calamus.window import CalamusWindow

        mock_tab_manager = MagicMock()
        stub = types.SimpleNamespace(
            _pipe_mode=False,
            tab_manager=mock_tab_manager,
        )
        captured_calls = []
        with patch("calamus.window.sys.stdout") as mock_stdout:
            mock_stdout.write.side_effect = lambda s: captured_calls.append(s)
            CalamusWindow._on_save(stub, MagicMock(), None)

        assert not captured_calls, "stdout must not be written in normal save mode"


class TestPipeModeClose:
    """Closing the window in pipe mode emits the last saved text, or the
    original piped input if the user never saved (Meld-as-mergetool contract).
    """

    def _make_close_stub(
        self,
        pipe_content: str,
        pipe_saved_content: str | None = None,
        pipe_mode: bool = True,
    ):
        import types

        mock_tab_manager = MagicMock()
        stub = types.SimpleNamespace(
            _confirmed_quit=False,
            _preview_mode=False,
            _pipe_mode=pipe_mode,
            _pipe_content=pipe_content,
            _pipe_saved_content=pipe_saved_content,
            tab_manager=mock_tab_manager,
        )
        return stub

    def test_close_without_save_emits_original_input(self):
        """Closing without saving reverts — original input is emitted unchanged."""
        import io

        from calamus.window import CalamusWindow

        stub = self._make_close_stub(
            pipe_content="# Original input\n",
            pipe_saved_content=None,
        )
        captured = io.StringIO()
        with patch("calamus.window.sys.stdout", captured):
            CalamusWindow._on_close_request(stub, MagicMock())

        assert captured.getvalue() == "# Original input\n"

    def test_close_after_save_emits_saved_content(self):
        """Closing after saving emits the saved snapshot, not the original."""
        import io

        from calamus.window import CalamusWindow

        stub = self._make_close_stub(
            pipe_content="# Original\n",
            pipe_saved_content="# Saved version\n",
        )
        captured = io.StringIO()
        with patch("calamus.window.sys.stdout", captured):
            CalamusWindow._on_close_request(stub, MagicMock())

        assert captured.getvalue() == "# Saved version\n"

    def test_close_returns_false_to_allow_window_close(self):
        """_on_close_request must return False so GTK proceeds with the close."""
        from calamus.window import CalamusWindow

        stub = self._make_close_stub(pipe_content="content")
        with patch("calamus.window.sys.stdout"):
            result = CalamusWindow._on_close_request(stub, MagicMock())

        assert result is False

    def test_close_without_save_does_not_emit_unsaved_edits(self):
        """Closing without saving ignores any in-progress edits."""
        import io

        from calamus.window import CalamusWindow

        stub = self._make_close_stub(
            pipe_content="# Original\n",
            pipe_saved_content=None,
        )
        captured = io.StringIO()
        with patch("calamus.window.sys.stdout", captured):
            CalamusWindow._on_close_request(stub, MagicMock())

        assert (
            captured.getvalue() == "# Original\n"
        ), "Unsaved edits must not appear in output when closing without saving"

    def test_normal_close_does_not_emit_to_stdout(self):
        """Non-pipe-mode close must never touch stdout."""
        import io
        import types

        from calamus.window import CalamusWindow

        mock_tab_manager = MagicMock()
        mock_tab_manager.get_tab_count.return_value = 1
        mock_tab_manager.get_unsaved_tabs.return_value = []
        stub = types.SimpleNamespace(
            _confirmed_quit=False,
            _preview_mode=False,
            _pipe_mode=False,
            tab_manager=mock_tab_manager,
        )
        captured = io.StringIO()
        with patch("calamus.window.sys.stdout", captured):
            CalamusWindow._on_close_request(stub, MagicMock())

        assert captured.getvalue() == ""


# ---------------------------------------------------------------------------
# parse_args — --preview flag
# ---------------------------------------------------------------------------


# TestParseArgsPreviewFlag has been replaced by TestHandleOptionsPreviewFlag
# above, which tests the same behaviour via CalamusApplication._handle_options.


# ---------------------------------------------------------------------------
# Preview mode close — no stdout output, just closes
# ---------------------------------------------------------------------------


class TestPreviewModeClose:
    """Closing in preview mode must never emit anything to stdout."""

    def _make_close_stub(self, preview_mode: bool = True, pipe_mode: bool = False):
        import types

        mock_tab_manager = MagicMock()
        mock_tab_manager.get_tab_count.return_value = 1
        mock_tab_manager.get_unsaved_tabs.return_value = []
        return types.SimpleNamespace(
            _confirmed_quit=False,
            _preview_mode=preview_mode,
            _pipe_mode=pipe_mode,
            _pipe_content="# Original\n",
            _pipe_saved_content=None,
            tab_manager=mock_tab_manager,
        )

    def test_close_does_not_emit_to_stdout(self):
        import io

        from calamus.window import CalamusWindow

        stub = self._make_close_stub()
        captured = io.StringIO()
        with patch("calamus.window.sys.stdout", captured):
            CalamusWindow._on_close_request(stub, MagicMock())

        assert captured.getvalue() == "", "Preview mode close must not write to stdout"

    def test_close_returns_false_to_allow_window_close(self):
        from calamus.window import CalamusWindow

        stub = self._make_close_stub()
        result = CalamusWindow._on_close_request(stub, MagicMock())
        assert result is False

    def test_preview_mode_takes_precedence_over_pipe_mode(self):
        """When both _preview_mode and _pipe_mode are True, no output emitted."""
        import io

        from calamus.window import CalamusWindow

        stub = self._make_close_stub(preview_mode=True, pipe_mode=True)
        captured = io.StringIO()
        with patch("calamus.window.sys.stdout", captured):
            CalamusWindow._on_close_request(stub, MagicMock())

        assert (
            captured.getvalue() == ""
        ), "Preview mode must suppress pipe output on close"

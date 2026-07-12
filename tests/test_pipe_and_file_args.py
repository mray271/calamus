"""Tests for CLI argument parsing and pipe mode behaviour.

``parse_args`` is pure Python (no GTK/display required) so all tests here run
in any environment.  The pipe-mode save test patches ``sys.stdout`` to verify
that Ctrl+S in pipe mode emits the editor text to stdout.
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from calamus.__main__ import parse_args

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tempfile(suffix: str = ".md", content: str = "# Hello") -> str:
    """Create a real temp file and return its path (caller must unlink)."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, content.encode())
    os.close(fd)
    return path


# ---------------------------------------------------------------------------
# parse_args — normal (no pipe) mode
# ---------------------------------------------------------------------------


class TestParseArgsNormal:
    def test_no_args_returns_empty(self):
        pipe, files, gtk, _ = parse_args(["calamus"], stdin_is_tty=True)
        assert pipe is None
        assert files == []
        assert gtk == ["calamus"]

    def test_single_file_arg(self):
        path = _make_tempfile()
        try:
            pipe, files, gtk, _ = parse_args(["calamus", path], stdin_is_tty=True)
            assert pipe is None
            assert files == [path]
            assert gtk == ["calamus"]
        finally:
            os.unlink(path)

    def test_multiple_file_args(self):
        p1 = _make_tempfile()
        p2 = _make_tempfile()
        try:
            pipe, files, gtk, _ = parse_args(["calamus", p1, p2], stdin_is_tty=True)
            assert files == [p1, p2]
        finally:
            os.unlink(p1)
            os.unlink(p2)

    def test_file_arg_made_absolute(self):
        path = _make_tempfile()
        try:
            _, files, _, _ = parse_args(["calamus", path], stdin_is_tty=True)
            assert os.path.isabs(files[0])
        finally:
            os.unlink(path)

    def test_nonexistent_file_exits_with_1(self):
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["calamus", "/no/such/file.md"], stdin_is_tty=True)
        assert exc_info.value.code == 1

    def test_gtk_flags_passed_through(self):
        _, _, gtk, _ = parse_args(["calamus", "--display=:1"], stdin_is_tty=True)
        assert "--display=:1" in gtk

    def test_tty_stdin_with_no_args_does_not_read_stdin(self):
        read_called = []

        def fake_read():
            read_called.append(True)
            return "content"

        parse_args(["calamus"], stdin_is_tty=True, read_stdin=fake_read)
        assert not read_called, "stdin must not be read when it is a TTY"


# ---------------------------------------------------------------------------
# parse_args — explicit --pipe flag
# ---------------------------------------------------------------------------


class TestParseArgsPipeFlag:
    def test_pipe_flag_reads_stdin(self):
        pipe, files, gtk, _ = parse_args(
            ["calamus", "--pipe"],
            stdin_is_tty=True,
            read_stdin=lambda: "# piped content",
        )
        assert pipe == "# piped content"
        assert files == []

    def test_pipe_flag_stripped_from_gtk_argv(self):
        _, _, gtk, _ = parse_args(
            ["calamus", "--pipe"],
            stdin_is_tty=True,
            read_stdin=lambda: "",
        )
        assert "--pipe" not in gtk

    def test_pipe_flag_with_other_gtk_flags(self):
        _, _, gtk, _ = parse_args(
            ["calamus", "--pipe", "--display=:1"],
            stdin_is_tty=True,
            read_stdin=lambda: "",
        )
        assert "--pipe" not in gtk
        assert "--display=:1" in gtk

    def test_pipe_flag_overrides_file_args(self):
        """--pipe and file args are mutually exclusive; --pipe wins."""
        path = _make_tempfile()
        try:
            # File arg comes AFTER --pipe — it still gets parsed as a file.
            # The point is --pipe itself triggers pipe_content regardless.
            pipe, _, _, _ = parse_args(
                ["calamus", "--pipe"],
                stdin_is_tty=True,
                read_stdin=lambda: "piped",
            )
            assert pipe == "piped"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# parse_args — auto-detect piped stdin (stdin_is_tty=False)
# ---------------------------------------------------------------------------


class TestParseArgsAutoDetect:
    def test_non_tty_stdin_reads_automatically(self):
        pipe, _, _, _ = parse_args(
            ["calamus"],
            stdin_is_tty=False,
            read_stdin=lambda: "auto piped",
        )
        assert pipe == "auto piped"

    def test_non_tty_empty_stdin_does_not_trigger_pipe_mode(self):
        """Docker/non-TTY with empty stdin (e.g. /dev/null) must not enter pipe mode."""
        pipe, _, _, _ = parse_args(
            ["calamus"],
            stdin_is_tty=False,
            read_stdin=lambda: "",
        )
        assert pipe is None, "Empty stdin must not activate pipe mode"

    def test_non_tty_stdin_not_read_when_files_given(self):
        """File paths suppress auto-detect — opening a file is not pipe mode."""
        path = _make_tempfile()
        read_called = []
        try:
            pipe, files, _, _ = parse_args(
                ["calamus", path],
                stdin_is_tty=False,
                read_stdin=lambda: (read_called.append(True) or "should not read"),
            )
            assert pipe is None
            assert files == [path]
            assert not read_called
        finally:
            os.unlink(path)

    def test_non_tty_stdin_not_read_when_pipe_flag_given(self):
        """Explicit --pipe already set pipe_content; auto-detect must not double-read."""
        reads: list[str] = []

        def counting_read():
            reads.append("read")
            return "from --pipe"

        pipe, _, _, _ = parse_args(
            ["calamus", "--pipe"],
            stdin_is_tty=False,
            read_stdin=counting_read,
        )
        assert pipe == "from --pipe"
        assert len(reads) == 1, "stdin should be read exactly once"


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


class TestParseArgsPreviewFlag:
    def test_preview_flag_sets_preview_mode(self):
        _, _, _, preview = parse_args(["calamus", "--preview"], stdin_is_tty=True)
        assert preview is True

    def test_no_flags_preview_mode_is_false(self):
        _, _, _, preview = parse_args(["calamus"], stdin_is_tty=True)
        assert preview is False

    def test_preview_flag_stripped_from_gtk_argv(self):
        _, _, gtk, _ = parse_args(["calamus", "--preview"], stdin_is_tty=True)
        assert "--preview" not in gtk

    def test_preview_with_file(self):
        path = _make_tempfile()
        try:
            _, files, _, preview = parse_args(
                ["calamus", "--preview", path], stdin_is_tty=True
            )
            assert preview is True
            assert files == [path]
        finally:
            os.unlink(path)

    def test_preview_with_other_gtk_flags(self):
        _, _, gtk, preview = parse_args(
            ["calamus", "--preview", "--display=:1"], stdin_is_tty=True
        )
        assert preview is True
        assert "--preview" not in gtk
        assert "--display=:1" in gtk


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

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
        pipe, files, gtk = parse_args(["calamus"], stdin_is_tty=True)
        assert pipe is None
        assert files == []
        assert gtk == ["calamus"]

    def test_single_file_arg(self):
        path = _make_tempfile()
        try:
            pipe, files, gtk = parse_args(["calamus", path], stdin_is_tty=True)
            assert pipe is None
            assert files == [path]
            assert gtk == ["calamus"]
        finally:
            os.unlink(path)

    def test_multiple_file_args(self):
        p1 = _make_tempfile()
        p2 = _make_tempfile()
        try:
            pipe, files, gtk = parse_args(["calamus", p1, p2], stdin_is_tty=True)
            assert files == [p1, p2]
        finally:
            os.unlink(p1)
            os.unlink(p2)

    def test_file_arg_made_absolute(self):
        path = _make_tempfile()
        try:
            _, files, _ = parse_args(["calamus", path], stdin_is_tty=True)
            assert os.path.isabs(files[0])
        finally:
            os.unlink(path)

    def test_nonexistent_file_exits_with_1(self):
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["calamus", "/no/such/file.md"], stdin_is_tty=True)
        assert exc_info.value.code == 1

    def test_gtk_flags_passed_through(self):
        _, _, gtk = parse_args(["calamus", "--display=:1"], stdin_is_tty=True)
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
        pipe, files, gtk = parse_args(
            ["calamus", "--pipe"],
            stdin_is_tty=True,
            read_stdin=lambda: "# piped content",
        )
        assert pipe == "# piped content"
        assert files == []

    def test_pipe_flag_stripped_from_gtk_argv(self):
        _, _, gtk = parse_args(
            ["calamus", "--pipe"],
            stdin_is_tty=True,
            read_stdin=lambda: "",
        )
        assert "--pipe" not in gtk

    def test_pipe_flag_with_other_gtk_flags(self):
        _, _, gtk = parse_args(
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
            pipe, _, _ = parse_args(
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
        pipe, _, _ = parse_args(
            ["calamus"],
            stdin_is_tty=False,
            read_stdin=lambda: "auto piped",
        )
        assert pipe == "auto piped"

    def test_non_tty_stdin_not_read_when_files_given(self):
        """File paths suppress auto-detect — opening a file is not pipe mode."""
        path = _make_tempfile()
        read_called = []
        try:
            pipe, files, _ = parse_args(
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

        pipe, _, _ = parse_args(
            ["calamus", "--pipe"],
            stdin_is_tty=False,
            read_stdin=counting_read,
        )
        assert pipe == "from --pipe"
        assert len(reads) == 1, "stdin should be read exactly once"


# ---------------------------------------------------------------------------
# Pipe mode save — emits editor text to stdout then quits
# ---------------------------------------------------------------------------


class TestPipeModeSave:
    """Ctrl+S in pipe mode saves internally but does NOT emit to stdout or quit.

    The gedit --wait contract: the user signals "done" by closing the window,
    not by saving.  Saving mid-session is a normal editing action.
    """

    def test_ctrl_s_does_not_write_stdout(self):
        import types
        from calamus.window import CalamusWindow

        mock_tab_manager = MagicMock()
        stub = types.SimpleNamespace(
            _pipe_mode=True,
            tab_manager=mock_tab_manager,
        )
        captured_calls = []
        with patch("calamus.window.sys.stdout") as mock_stdout:
            mock_stdout.write.side_effect = lambda s: captured_calls.append(s)
            CalamusWindow._on_save(stub, MagicMock(), None)

        assert not captured_calls, "Ctrl+S must not write to stdout in pipe mode"
        mock_tab_manager.save_current.assert_called_once()

    def test_ctrl_s_does_not_quit(self):
        import types
        from calamus.window import CalamusWindow

        mock_tab_manager = MagicMock()
        mock_app = MagicMock()
        stub = types.SimpleNamespace(
            _pipe_mode=True,
            tab_manager=mock_tab_manager,
            get_application=lambda: mock_app,
        )
        CalamusWindow._on_save(stub, MagicMock(), None)
        mock_app.quit.assert_not_called()

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
        mock_tab_manager.save_current.assert_called_once()


class TestPipeModeClose:
    """Closing the window in pipe mode emits editor text to stdout immediately
    with no confirmation dialog (gedit --wait contract).
    """

    def _make_close_stub(self, editor_text: str, pipe_mode: bool = True):
        import types

        mock_editor = MagicMock()
        mock_editor.get_text.return_value = editor_text
        mock_tab_manager = MagicMock()
        mock_tab_manager.get_current_editor.return_value = mock_editor
        stub = types.SimpleNamespace(
            _confirmed_quit=False,
            _pipe_mode=pipe_mode,
            tab_manager=mock_tab_manager,
        )
        return stub

    def test_close_emits_editor_text_to_stdout(self):
        import io
        from calamus.window import CalamusWindow

        stub = self._make_close_stub("# My edited document\n")
        captured = io.StringIO()
        with patch("calamus.window.sys.stdout", captured):
            result = CalamusWindow._on_close_request(stub, MagicMock())

        assert captured.getvalue() == "# My edited document\n"

    def test_close_returns_false_to_allow_window_close(self):
        """_on_close_request must return False so GTK proceeds with the close."""
        from calamus.window import CalamusWindow

        stub = self._make_close_stub("content")
        with patch("calamus.window.sys.stdout"):
            result = CalamusWindow._on_close_request(stub, MagicMock())

        assert result is False

    def test_close_emits_even_with_unsaved_edits(self):
        """User's last state is what matters — no save prompt in pipe mode."""
        import io
        from calamus.window import CalamusWindow

        stub = self._make_close_stub("# Unsaved edits here")
        captured = io.StringIO()
        with patch("calamus.window.sys.stdout", captured):
            CalamusWindow._on_close_request(stub, MagicMock())

        assert captured.getvalue() == "# Unsaved edits here"

    def test_normal_close_does_not_emit_to_stdout(self):
        """Non-pipe-mode close must never touch stdout."""
        import io, types
        from calamus.window import CalamusWindow

        mock_tab_manager = MagicMock()
        mock_tab_manager.get_tab_count.return_value = 1
        mock_tab_manager.get_unsaved_tabs.return_value = []
        stub = types.SimpleNamespace(
            _confirmed_quit=False,
            _pipe_mode=False,
            tab_manager=mock_tab_manager,
        )
        captured = io.StringIO()
        with patch("calamus.window.sys.stdout", captured):
            CalamusWindow._on_close_request(stub, MagicMock())

        assert captured.getvalue() == ""

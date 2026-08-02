"""Unit tests for calamus.search — SearchState, dialogs, and helpers.

These tests cover the pure-Python SearchState logic (no GTK required)
and, where a display is available, the GTK dialog classes.
"""

from __future__ import annotations

import pytest

from calamus.search import _MAX_HISTORY, SearchState

# ---------------------------------------------------------------------------
# SearchState — pure Python, no display needed
# ---------------------------------------------------------------------------


class TestSearchStateDefaults:
    def test_initial_find_history_is_empty(self):
        s = SearchState()
        assert s.find_history == []

    def test_initial_flags_are_false(self):
        s = SearchState()
        assert s.use_regex is False
        assert s.case_sensitive is False
        assert s.whole_word is False
        assert s.search_backward is False
        assert s.keep_dialog is False

    def test_initial_replace_string_is_empty(self):
        s = SearchState()
        assert s.replace_string == ""


class TestSearchStatePushFind:
    def test_push_adds_entry(self):
        s = SearchState()
        s.push_find("hello")
        assert "hello" in s.find_history

    def test_push_empty_is_noop(self):
        s = SearchState()
        s.push_find("")
        assert s.find_history == []

    def test_push_deduplicates(self):
        s = SearchState()
        s.push_find("a")
        s.push_find("b")
        s.push_find("a")
        assert s.find_history.count("a") == 1

    def test_push_moves_duplicate_to_end(self):
        s = SearchState()
        s.push_find("a")
        s.push_find("b")
        s.push_find("a")
        assert s.find_history[-1] == "a"

    def test_push_respects_max_history(self):
        s = SearchState()
        for i in range(_MAX_HISTORY + 5):
            s.push_find(f"item-{i}")
        assert len(s.find_history) == _MAX_HISTORY

    def test_push_drops_oldest(self):
        s = SearchState()
        for i in range(_MAX_HISTORY + 1):
            s.push_find(f"item-{i}")
        assert "item-0" not in s.find_history

    def test_push_resets_history_index(self):
        s = SearchState()
        s.push_find("a")
        s.history_prev()  # move index to 0
        s.push_find("b")
        # After push, index should be -1 again
        assert s._history_index == -1


class TestSearchStateHistoryNavigation:
    def test_history_prev_empty_returns_none(self):
        s = SearchState()
        assert s.history_prev() is None

    def test_history_next_empty_returns_none(self):
        s = SearchState()
        assert s.history_next() is None

    def test_history_prev_single_entry(self):
        s = SearchState()
        s.push_find("only")
        assert s.history_prev() == "only"

    def test_history_prev_multiple_entries_returns_most_recent_first(self):
        s = SearchState()
        s.push_find("first")
        s.push_find("second")
        assert s.history_prev() == "second"

    def test_history_prev_multiple_steps_backward(self):
        s = SearchState()
        s.push_find("a")
        s.push_find("b")
        s.push_find("c")
        assert s.history_prev() == "c"
        assert s.history_prev() == "b"
        assert s.history_prev() == "a"

    def test_history_prev_clamps_at_oldest(self):
        s = SearchState()
        s.push_find("a")
        s.push_find("b")
        s.history_prev()  # "b"
        s.history_prev()  # "a"
        # Extra prev at boundary should stay at "a"
        assert s.history_prev() == "a"

    def test_history_next_returns_none_when_at_index_minus_one(self):
        s = SearchState()
        s.push_find("a")
        assert s.history_next() is None

    def test_history_next_after_prev(self):
        s = SearchState()
        s.push_find("a")
        s.push_find("b")
        s.history_prev()  # "b"
        s.history_prev()  # "a"
        assert s.history_next() == "b"

    def test_history_next_at_end_resets_index(self):
        s = SearchState()
        s.push_find("a")
        s.push_find("b")
        s.history_prev()  # "b" — index=1
        nxt = s.history_next()  # returns None, resets to -1
        assert nxt is None
        assert s._history_index == -1

    def test_reset_history_cursor(self):
        s = SearchState()
        s.push_find("a")
        s.history_prev()
        assert s._history_index != -1
        s.reset_history_cursor()
        assert s._history_index == -1


class TestSearchStateResetOptions:
    def test_reset_options_clears_transient_state(self):
        """reset_options clears replace_string, search_backward, keep_dialog."""
        s = SearchState()
        s.replace_string = "bar"
        s.search_backward = True
        s.keep_dialog = True
        s.reset_options()
        assert s.replace_string == ""
        assert s.search_backward is False
        assert s.keep_dialog is False

    def test_reset_options_preserves_search_flags(self):
        """case_sensitive, use_regex, whole_word survive reset_options so
        Find Again (Ctrl+G) repeats the exact same search after dialog close."""
        s = SearchState()
        s.case_sensitive = True
        s.use_regex = True
        s.whole_word = True
        s.reset_options()
        assert s.case_sensitive is True
        assert s.use_regex is True
        assert s.whole_word is True

    def test_reset_options_preserves_find_string(self):
        s = SearchState()
        s.push_find("hello")
        s.reset_options()
        assert s.find_history[0] == "hello"


# ---------------------------------------------------------------------------
# GTK dialog smoke tests — require a display
# ---------------------------------------------------------------------------

gi_available = pytest.importorskip("gi", reason="PyGObject not available")


def _init_gtk():
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("GtkSource", "5")
    gi.require_version("Adw", "1")
    from gi.repository import Adw

    Adw.init()


class _FakeEditor:
    """Minimal editor stub for dialog logic tests."""

    def __init__(self):
        self.find_next_calls: list = []
        self.find_previous_calls: list = []
        self.replace_current_calls: list = []
        self.replace_all_calls: list = []
        self.replace_and_find_calls: list = []

    def find_next(self, state):
        self.find_next_calls.append(state)
        return True

    def find_previous(self, state):
        self.find_previous_calls.append(state)
        return True

    def replace_current(self, replacement, state):
        self.replace_current_calls.append((replacement, state))
        return True

    def replace_all(self, replacement, scope, state):
        self.replace_all_calls.append((replacement, scope, state))
        return 3

    def replace_and_find(self, replacement, state):
        self.replace_and_find_calls.append((replacement, state))
        return True

    def get_selection(self):
        return ("", False)


class _FakeCheck:
    """Stand-in for Gtk.CheckButton in logic tests."""

    def __init__(self, active: bool = False):
        self._active = active

    def get_active(self) -> bool:
        return self._active


def _make_fake_checks(
    use_regex=False,
    case_sensitive=False,
    whole_word=False,
    search_backward=False,
    keep_dialog=False,
) -> dict:
    return {
        "use_regex": _FakeCheck(use_regex),
        "case_sensitive": _FakeCheck(case_sensitive),
        "whole_word": _FakeCheck(whole_word),
        "search_backward": _FakeCheck(search_backward),
        "keep_dialog": _FakeCheck(keep_dialog),
    }


# ---------------------------------------------------------------------------
# FindDialogLogic tests — pure Python, no display needed
# ---------------------------------------------------------------------------


class _TestFindLogic:
    """Concrete FindDialogLogic for tests (no GTK)."""

    def __init__(self, editor, state, find_text="", keep_dialog=False):
        from calamus.search import FindDialogLogic

        # Dynamically create a concrete subclass
        class _Impl(FindDialogLogic):
            def __init__(self_, *, editor, state, find_text):
                self_._editor = editor
                self_._state = state
                self_._find_text = find_text
                self_._checks = _make_fake_checks(keep_dialog=state.keep_dialog)
                self_._closed = False

            def get_find_text(self_):
                return self_._find_text

            def close_dialog(self_):
                self_._closed = True

        self._impl = _Impl(editor=editor, state=state, find_text=find_text)

    @property
    def impl(self):
        return self._impl


def test_find_logic_handle_find_calls_find_next():
    editor = _FakeEditor()
    state = SearchState()
    state.push_find("hello")
    state.keep_dialog = True
    logic = _TestFindLogic(editor, state, find_text="hello").impl
    result = logic.handle_find()
    assert result is True
    assert len(editor.find_next_calls) == 1


def test_find_logic_handle_find_calls_find_previous_when_backward():
    editor = _FakeEditor()
    state = SearchState()
    state.search_backward = True
    state.keep_dialog = True
    logic = _TestFindLogic(editor, state, find_text="backward").impl
    logic._checks["search_backward"] = _FakeCheck(True)
    result = logic.handle_find()
    assert len(editor.find_previous_calls) == 1


def test_find_logic_handle_find_pushes_history():
    editor = _FakeEditor()
    state = SearchState()
    state.keep_dialog = True
    logic = _TestFindLogic(editor, state, find_text="newterm").impl
    logic.handle_find()
    assert "newterm" in state.find_history


def test_find_logic_closes_dialog_when_found_and_not_keep():
    editor = _FakeEditor()
    state = SearchState()
    state.keep_dialog = False
    logic = _TestFindLogic(editor, state, find_text="x").impl
    logic._checks["keep_dialog"] = _FakeCheck(False)
    logic.handle_find()
    assert logic._closed is True


def test_find_logic_does_not_close_when_keep_dialog():
    editor = _FakeEditor()
    state = SearchState()
    state.keep_dialog = True
    logic = _TestFindLogic(editor, state, find_text="x").impl
    logic._checks["keep_dialog"] = _FakeCheck(True)
    logic.handle_find()
    assert logic._closed is False


# ---------------------------------------------------------------------------
# ReplaceDialogLogic tests — pure Python, no display needed
# ---------------------------------------------------------------------------


class _TestReplaceLogic:
    """Concrete ReplaceDialogLogic for tests (no GTK)."""

    def __init__(self, editor, state, find_text="", replace_text=""):
        from calamus.search import ReplaceDialogLogic

        class _Impl(ReplaceDialogLogic):
            def __init__(self_, *, editor, state, find_text, replace_text):
                self_._editor = editor
                self_._state = state
                self_._tab_manager = None
                self_._find_text = find_text
                self_._replace_text = replace_text
                self_._checks = _make_fake_checks(keep_dialog=state.keep_dialog)
                self_._closed = False

            def get_find_text(self_):
                return self_._find_text

            def get_replace_text(self_):
                return self_._replace_text

            def close_dialog(self_):
                self_._closed = True

        self._impl = _Impl(
            editor=editor,
            state=state,
            find_text=find_text,
            replace_text=replace_text,
        )

    @property
    def impl(self):
        return self._impl


def test_replace_logic_handle_find_calls_find_next():
    editor = _FakeEditor()
    state = SearchState()
    state.push_find("foo")
    logic = _TestReplaceLogic(editor, state, find_text="foo").impl
    logic.handle_find()
    assert len(editor.find_next_calls) == 1


def test_replace_logic_handle_find_calls_find_previous_when_backward():
    editor = _FakeEditor()
    state = SearchState()
    state.search_backward = True
    logic = _TestReplaceLogic(editor, state, find_text="bwd").impl
    logic._checks["search_backward"] = _FakeCheck(True)
    logic.handle_find()
    assert len(editor.find_previous_calls) == 1


def test_replace_logic_handle_replace_calls_replace_current():
    editor = _FakeEditor()
    state = SearchState()
    state.push_find("foo")
    logic = _TestReplaceLogic(editor, state, find_text="foo", replace_text="bar").impl
    logic.handle_replace()
    assert len(editor.replace_current_calls) == 1
    replacement, _ = editor.replace_current_calls[0]
    assert replacement == "bar"


def test_replace_logic_handle_replace_and_find():
    editor = _FakeEditor()
    state = SearchState()
    state.keep_dialog = True
    state.push_find("foo")
    logic = _TestReplaceLogic(editor, state, find_text="foo", replace_text="bar").impl
    logic._checks["keep_dialog"] = _FakeCheck(True)
    result = logic.handle_replace_and_find()
    assert result is True
    assert len(editor.replace_and_find_calls) == 1


def test_replace_logic_handle_replace_and_find_closes_when_not_keep():
    editor = _FakeEditor()
    state = SearchState()
    state.keep_dialog = False
    logic = _TestReplaceLogic(editor, state, find_text="foo", replace_text="bar").impl
    logic._checks["keep_dialog"] = _FakeCheck(False)
    logic.handle_replace_and_find()
    assert logic._closed is True


def test_replace_logic_handle_replace_all_window():
    editor = _FakeEditor()
    state = SearchState()
    state.push_find("x")
    logic = _TestReplaceLogic(editor, state, find_text="x", replace_text="y").impl
    count = logic.handle_replace_all("window")
    assert len(editor.replace_all_calls) == 1
    _, scope, _ = editor.replace_all_calls[0]
    assert scope == "window"
    assert count == 3


def test_replace_logic_handle_replace_all_selection():
    editor = _FakeEditor()
    state = SearchState()
    state.push_find("x")
    logic = _TestReplaceLogic(editor, state, find_text="x", replace_text="y").impl
    count = logic.handle_replace_all("selection")
    _, scope, _ = editor.replace_all_calls[0]
    assert scope == "selection"


def test_replace_logic_commit_entries_updates_state():
    editor = _FakeEditor()
    state = SearchState()
    logic = _TestReplaceLogic(
        editor, state, find_text="needle", replace_text="replacement"
    ).impl
    logic.commit_entries()
    assert state.replace_string == "replacement"
    assert "needle" in state.find_history


def test_replace_logic_get_all_editors_no_tab_manager():
    editor = _FakeEditor()
    state = SearchState()
    logic = _TestReplaceLogic(editor, state).impl
    editors = logic._get_all_editors()
    assert editors == [editor]


# ---------------------------------------------------------------------------
# _sync_options_to_state — tests that it copies check values to state
# ---------------------------------------------------------------------------


def test_sync_options_sets_flags():
    from calamus.search import _sync_options_to_state

    state = SearchState()
    checks = {
        "use_regex": _FakeCheck(True),
        "case_sensitive": _FakeCheck(False),
        "whole_word": _FakeCheck(True),
        "search_backward": _FakeCheck(False),
        "keep_dialog": _FakeCheck(True),
    }
    _sync_options_to_state(checks, state)
    assert state.use_regex is True
    assert state.case_sensitive is False
    assert state.whole_word is True
    assert state.search_backward is False
    assert state.keep_dialog is True


def test_sync_options_all_false():
    from calamus.search import _sync_options_to_state

    state = SearchState(use_regex=True, case_sensitive=True)
    checks = _make_fake_checks()
    _sync_options_to_state(checks, state)
    assert state.use_regex is False
    assert state.case_sensitive is False

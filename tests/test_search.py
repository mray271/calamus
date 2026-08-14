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
        assert s.match_diacritics is False
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


class TestSearchStateMakeDialogScratch:
    def test_scratch_starts_blank(self):
        """make_dialog_scratch returns a fresh state with all flags False."""
        live = SearchState()
        live.case_sensitive = True
        live.use_regex = True
        live.push_find("hello")
        scratch = live.make_dialog_scratch()
        assert scratch.case_sensitive is False
        assert scratch.use_regex is False
        assert scratch.match_diacritics is False
        assert scratch.whole_word is False
        assert scratch.search_backward is False
        assert scratch.keep_dialog is False
        assert scratch.replace_string == ""

    def test_scratch_shares_history_lists(self):
        """Scratch and live share the same history list objects."""
        live = SearchState()
        live.push_find("a")
        scratch = live.make_dialog_scratch()
        assert scratch.find_history is live.find_history
        assert scratch.replace_history is live.replace_history

    def test_scratch_history_recall_sees_live_history(self):
        """↑/↓ recall on the scratch reflects history pushed to live."""
        live = SearchState()
        live.push_find("first")
        live.push_find("second")
        scratch = live.make_dialog_scratch()
        assert scratch.history_prev() == "second"


class TestSearchStateCommitTo:
    def test_commit_copies_flags_and_strings(self):
        """commit_to copies all option flags and replace_string to target."""
        scratch = SearchState()
        scratch.case_sensitive = True
        scratch.use_regex = True
        scratch.match_diacritics = True
        scratch.whole_word = True
        scratch.search_backward = True
        scratch.keep_dialog = True
        scratch.replace_string = "bar"
        live = SearchState()
        scratch.commit_to(live)
        assert live.case_sensitive is True
        assert live.use_regex is True
        assert live.match_diacritics is True
        assert live.whole_word is True
        assert live.search_backward is True
        assert live.keep_dialog is True
        assert live.replace_string == "bar"

    def test_commit_does_not_touch_original(self):
        """commit_to does not modify the source state."""
        scratch = SearchState()
        scratch.case_sensitive = True
        live = SearchState()
        scratch.commit_to(live)
        # scratch unchanged
        assert scratch.case_sensitive is True

    def test_live_unchanged_without_commit(self):
        """Modifying scratch without commit leaves live state untouched."""
        live = SearchState()
        live.case_sensitive = True
        scratch = live.make_dialog_scratch()
        scratch.case_sensitive = False
        # live was not committed to
        assert live.case_sensitive is True


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
        self._buffer = _FakeBuffer()

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

    def get_buffer(self):
        return self._buffer


class _FakeIter:
    def __init__(self, offset: int):
        self._offset = offset

    def get_offset(self) -> int:
        return self._offset


class _FakeBuffer:
    def __init__(self):
        self._selection = False
        self._selection_start = 0
        self._selection_end = 0
        self.cursor_offset = 0

    def get_has_selection(self):
        return self._selection

    def get_selection_bounds(self):
        return _FakeIter(self._selection_start), _FakeIter(self._selection_end)

    def place_cursor(self, iterator):
        self.cursor_offset = iterator.get_offset()

    def get_iter_at_offset(self, offset: int):
        return _FakeIter(offset)


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

    def __init__(
        self,
        editor,
        state,
        find_text="",
        keep_dialog=False,
        findable_resolver=None,
    ):
        from calamus.search import FindDialogLogic

        # Dynamically create a concrete subclass
        class _Impl(FindDialogLogic):
            def __init__(self_, *, editor, state, find_text, findable_resolver):
                self_._findable = editor
                self_._findable_resolver = findable_resolver
                # In tests, scratch == live so assertions on state work directly.
                self_._live_state = state
                self_._state = state.make_dialog_scratch()
                self_._find_text = find_text
                self_._checks = _make_fake_checks(keep_dialog=keep_dialog)
                self_._closed = False

            def get_find_text(self_):
                return self_._find_text

            def close_dialog(self_):
                self_._closed = True

        self._impl = _Impl(
            editor=editor,
            state=state,
            find_text=find_text,
            findable_resolver=findable_resolver,
        )

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


def test_find_logic_handle_find_copies_match_diacritics():
    editor = _FakeEditor()
    state = SearchState()
    state.keep_dialog = True
    logic = _TestFindLogic(editor, state, find_text="cafe").impl
    logic._checks["match_diacritics"] = _FakeCheck(True)
    logic.handle_find()
    assert editor.find_next_calls[0].match_diacritics is True


def test_find_logic_closes_dialog_when_found_and_not_keep():
    editor = _FakeEditor()
    state = SearchState()
    state.keep_dialog = False
    logic = _TestFindLogic(editor, state, find_text="x").impl
    logic._checks["keep_dialog"] = _FakeCheck(False)
    logic.handle_find()
    assert logic._closed is True


def test_find_logic_closes_dialog_when_not_found_and_not_keep():
    editor = _FakeEditor()
    state = SearchState()
    state.keep_dialog = False
    logic = _TestFindLogic(editor, state, find_text="missing").impl
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


def test_find_logic_uses_latest_resolved_findable():
    editor1 = _FakeEditor()
    editor2 = _FakeEditor()
    state = SearchState()
    state.keep_dialog = True
    active = {"findable": editor1}

    def resolve():
        return active["findable"]

    logic = _TestFindLogic(
        editor1, state, find_text="x", findable_resolver=resolve
    ).impl
    logic.handle_find()
    active["findable"] = editor2
    logic.handle_find()

    assert len(editor1.find_next_calls) == 1
    assert len(editor2.find_next_calls) == 1


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
                # In tests, scratch == live so assertions on state work directly.
                self_._live_state = state
                self_._state = state.make_dialog_scratch()
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
    assert len(editor.find_next_calls) == 1
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
    assert len(editor.find_next_calls) == 2
    assert len(editor.replace_current_calls) == 1


def test_replace_logic_handle_replace_and_find_honors_backward():
    editor = _FakeEditor()
    state = SearchState()
    state.search_backward = True
    state.keep_dialog = True
    state.push_find("foo")
    logic = _TestReplaceLogic(editor, state, find_text="foo", replace_text="bar").impl
    logic._checks["search_backward"] = _FakeCheck(True)
    result = logic.handle_replace_and_find()
    assert result is True
    assert len(editor.find_previous_calls) == 2
    assert len(editor.replace_current_calls) == 1


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


def test_find_dialog_entry_activate_triggers_find():
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from calamus.search_dialogs import FindDialog

    _init_gtk()

    class _Editor(_FakeEditor):
        pass

    editor = _Editor()
    state = SearchState()
    dialog = FindDialog(editor, state)
    try:
        assert "match_diacritics" in dialog._checks
        assert dialog._checks["match_diacritics"].get_active() is False
        dialog._find_entry.set_text("needle")
        dialog.handle_find()
        assert len(editor.find_next_calls) == 1
    finally:
        dialog.close()


def test_replace_dialog_entry_activate_triggers_replace():
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from calamus.search_dialogs import ReplaceDialog

    _init_gtk()

    editor = _FakeEditor()
    state = SearchState()
    dialog = ReplaceDialog(editor, state)
    try:
        dialog._find_entry.set_text("needle")
        dialog._replace_entry.set_text("replacement")
        dialog.handle_replace()
        assert len(editor.replace_current_calls) == 1
    finally:
        dialog.close()


def test_find_dialog_default_widget_is_find():
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from calamus.search_dialogs import FindDialog

    _init_gtk()

    dialog = FindDialog(_FakeEditor(), SearchState())
    try:
        default = dialog.get_default_widget()
        assert default is not None
        assert default.get_label() == "Find"
    finally:
        dialog.close()


def test_replace_dialog_default_widget_is_replace():
    gi = pytest.importorskip("gi")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from calamus.search_dialogs import ReplaceDialog

    _init_gtk()

    dialog = ReplaceDialog(_FakeEditor(), SearchState())
    try:
        default = dialog.get_default_widget()
        assert default is not None
        assert default.get_label() == "Replace"
    finally:
        dialog.close()


def test_find_dialog_enter_works_when_checkbox_has_focus():
    from calamus.search_dialogs import FindDialog, _activate_dialog_default

    _init_gtk()

    editor = _FakeEditor()
    dialog = FindDialog(editor, SearchState())
    try:
        dialog._find_entry.set_text("needle")
        dialog._checks["keep_dialog"].grab_focus()
        _activate_dialog_default(dialog)
        assert len(editor.find_next_calls) == 1
    finally:
        dialog.close()


def test_replace_dialog_enter_uses_replace_default_when_checkbox_has_focus():
    from calamus.search_dialogs import ReplaceDialog, _activate_dialog_default

    _init_gtk()

    editor = _FakeEditor()
    dialog = ReplaceDialog(editor, SearchState())
    try:
        dialog._find_entry.set_text("needle")
        dialog._replace_entry.set_text("replacement")
        dialog._checks["keep_dialog"].grab_focus()
        _activate_dialog_default(dialog)
        assert len(editor.find_next_calls) == 1
        assert len(editor.replace_current_calls) == 1
        assert len(editor.replace_and_find_calls) == 0
    finally:
        dialog.close()


def test_replace_dialog_enter_honors_backward_search_when_checkbox_has_focus():
    from calamus.search_dialogs import ReplaceDialog, _activate_dialog_default

    _init_gtk()

    editor = _FakeEditor()
    dialog = ReplaceDialog(editor, SearchState())
    try:
        dialog._find_entry.set_text("needle")
        dialog._replace_entry.set_text("replacement")
        dialog._checks["search_backward"].set_active(True)
        dialog._checks["keep_dialog"].grab_focus()
        _activate_dialog_default(dialog)
        assert len(editor.find_previous_calls) == 1
        assert len(editor.replace_current_calls) == 1
    finally:
        dialog.close()


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

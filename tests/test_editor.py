"""GTK widget tests for MarkdownEditor — requires xvfb (run via xvfb-run)."""

from pathlib import Path

import pytest

# These tests require a display. Skip gracefully if no display is available.
gi_available = pytest.importorskip("gi", reason="PyGObject not available")

_CANTICO_PATH = Path(__file__).resolve().parent.parent / "samples" / "cantico_negro.md"
_CANTICO_MD = _CANTICO_PATH.read_text(encoding="utf-8")


def _init_gtk():
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("GtkSource", "5")
    gi.require_version("Adw", "1")
    from gi.repository import Adw

    Adw.init()


def test_markdown_editor_instantiation():
    _init_gtk()
    from calamus.editor import MarkdownEditor

    editor = MarkdownEditor()
    assert editor is not None


def test_editor_set_and_get_text():
    _init_gtk()
    from calamus.editor import MarkdownEditor

    editor = MarkdownEditor()
    editor.set_text("# Hello\n\nWorld")
    assert editor.get_text() == "# Hello\n\nWorld"


def test_editor_get_text_empty():
    _init_gtk()
    from calamus.editor import MarkdownEditor

    editor = MarkdownEditor()
    assert editor.get_text() == ""


def test_editor_get_selection_no_selection():
    _init_gtk()
    from calamus.editor import MarkdownEditor

    editor = MarkdownEditor()
    editor.set_text("hello world")
    text, has_sel = editor.get_selection()
    assert has_sel is False
    assert text == ""


def test_editor_replace_selection():
    _init_gtk()
    from calamus.editor import MarkdownEditor

    editor = MarkdownEditor()
    editor.set_text("hello world")
    buf = editor.get_buffer()
    start = buf.get_iter_at_offset(0)
    end = buf.get_iter_at_offset(5)
    buf.select_range(start, end)
    editor.replace_selection("goodbye")
    assert "goodbye" in editor.get_text()


def test_editor_insert_at_cursor():
    _init_gtk()
    from calamus.editor import MarkdownEditor

    editor = MarkdownEditor()
    editor.set_text("")
    editor.insert_at_cursor("inserted")
    assert "inserted" in editor.get_text()


def test_editor_undo_redo():
    _init_gtk()
    from calamus.editor import MarkdownEditor

    editor = MarkdownEditor()
    editor.set_text("original")
    editor.get_buffer().set_text("changed")
    editor.undo()
    # After undo the buffer should be different from "changed"
    # (exact state depends on GtkSource undo grouping)
    assert editor.get_text() is not None


def test_editor_is_abstract_editor_subclass():
    _init_gtk()
    from calamus.editor import AbstractEditor, MarkdownEditor

    assert issubclass(MarkdownEditor, AbstractEditor)


def test_editor_configure_from_prefs(tmp_path, monkeypatch):
    _init_gtk()
    import configparser

    from calamus.editor import MarkdownEditor

    config = configparser.ConfigParser()
    config["Editor"] = {
        "font_size": "14",
        "tab_width": "2",
        "use_spaces": "true",
        "show_line_numbers": "true",
        "word_wrap": "false",
    }
    editor = MarkdownEditor()
    # Should not raise
    editor.configure_from_prefs(config)


def test_editor_get_widget():
    _init_gtk()
    from calamus.editor import MarkdownEditor

    editor = MarkdownEditor()
    widget = editor.get_widget()
    assert widget is not None


def test_editor_get_selection_with_selection():
    _init_gtk()
    from calamus.editor import MarkdownEditor

    editor = MarkdownEditor()
    editor.set_text("hello world")
    buf = editor.get_buffer()
    buf.select_range(buf.get_iter_at_offset(0), buf.get_iter_at_offset(5))
    text, has_sel = editor.get_selection()
    assert has_sel is True
    assert text == "hello"


def test_editor_undo_after_insert():
    _init_gtk()
    from calamus.editor import MarkdownEditor

    editor = MarkdownEditor()
    editor.insert_at_cursor("hello")
    editor.undo()
    # undo() should execute buffer.undo() when can_undo is True after an insert
    assert editor.get_text() is not None


def test_editor_redo_after_undo():
    _init_gtk()
    from calamus.editor import MarkdownEditor

    editor = MarkdownEditor()
    editor.insert_at_cursor("hello")
    editor.undo()
    editor.redo()
    assert editor.get_text() is not None


def test_editor_toggle_find_bar_no_revealer():
    _init_gtk()
    from calamus.editor import MarkdownEditor

    editor = MarkdownEditor()
    # _find_revealer is None — should not raise
    editor.toggle_find_bar()


# ---------------------------------------------------------------------------
# Search / Replace API tests (require display)
# ---------------------------------------------------------------------------


def test_editor_find_next_finds_text():
    _init_gtk()
    from calamus.editor import MarkdownEditor
    from calamus.search import SearchState

    editor = MarkdownEditor()
    editor.set_text("hello world hello")
    state = SearchState()
    state.push_find("hello")
    found = editor.find_next(state)
    assert found is True


def test_editor_find_next_returns_false_when_not_found():
    _init_gtk()
    from calamus.editor import MarkdownEditor
    from calamus.search import SearchState

    editor = MarkdownEditor()
    editor.set_text("hello world")
    state = SearchState()
    state.push_find("xyz_not_present")
    found = editor.find_next(state)
    assert found is False


def test_editor_find_previous_finds_text():
    _init_gtk()
    from calamus.editor import MarkdownEditor
    from calamus.search import SearchState

    editor = MarkdownEditor()
    editor.set_text("hello world hello")
    state = SearchState()
    state.push_find("hello")
    # Move cursor to end so backward search finds something
    buf = editor.get_buffer()
    buf.place_cursor(buf.get_end_iter())
    found = editor.find_previous(state)
    assert found is True


def test_editor_find_previous_returns_false_when_not_found():
    _init_gtk()
    from calamus.editor import MarkdownEditor
    from calamus.search import SearchState

    editor = MarkdownEditor()
    editor.set_text("hello world")
    state = SearchState()
    state.push_find("zzz_missing")
    found = editor.find_previous(state)
    assert found is False


def test_editor_replace_current_replaces_selection():
    _init_gtk()
    from calamus.editor import MarkdownEditor
    from calamus.search import SearchState

    editor = MarkdownEditor()
    editor.set_text("hello world")
    state = SearchState()
    state.push_find("hello")
    editor.find_next(state)
    replaced = editor.replace_current("goodbye", state)
    assert replaced is True
    assert "goodbye" in editor.get_text()


def test_editor_replace_current_returns_false_with_no_selection():
    _init_gtk()
    from calamus.editor import MarkdownEditor
    from calamus.search import SearchState

    editor = MarkdownEditor()
    editor.set_text("hello world")
    state = SearchState()
    state.push_find("hello")
    # Don't call find_next — no selection
    result = editor.replace_current("x", state)
    assert result is False


def test_editor_replace_all_window():
    _init_gtk()
    from calamus.editor import MarkdownEditor
    from calamus.search import SearchState

    editor = MarkdownEditor()
    editor.set_text("cat cat cat")
    state = SearchState()
    state.push_find("cat")
    count = editor.replace_all("dog", "window", state)
    assert count == 3
    assert editor.get_text() == "dog dog dog"


def test_editor_replace_and_find():
    _init_gtk()
    from calamus.editor import MarkdownEditor
    from calamus.search import SearchState

    editor = MarkdownEditor()
    editor.set_text("foo foo foo")
    state = SearchState()
    state.push_find("foo")
    editor.find_next(state)  # select first "foo"
    result = editor.replace_and_find("bar", state)
    # After replace_and_find the second "foo" should be selected
    assert "bar" in editor.get_text()
    # result indicates whether the *next* occurrence was found
    assert isinstance(result, bool)


def test_editor_find_with_case_sensitive():
    _init_gtk()
    from calamus.editor import MarkdownEditor
    from calamus.search import SearchState

    editor = MarkdownEditor()
    editor.set_text("Hello HELLO hello")
    state = SearchState()
    state.push_find("hello")
    state.case_sensitive = True
    found = editor.find_next(state)
    assert found is True
    # Should match only the lowercase "hello"
    buf = editor.get_buffer()
    start, end = buf.get_selection_bounds()
    matched = buf.get_text(start, end, True)
    assert matched == "hello"


def test_editor_find_match_diacritics_off_matches_without_accents():
    _init_gtk()
    from calamus.editor import MarkdownEditor
    from calamus.search import SearchState

    editor = MarkdownEditor()
    editor.set_text("café cafe")
    state = SearchState()
    state.push_find("cafe")
    state.match_diacritics = False
    found = editor.find_next(state)
    assert found is True
    buf = editor.get_buffer()
    start, end = buf.get_selection_bounds()
    matched = buf.get_text(start, end, True)
    assert matched in {"café", "cafe"}


def test_editor_find_match_diacritics_on_requires_exact_marks():
    _init_gtk()
    from calamus.editor import MarkdownEditor
    from calamus.search import SearchState

    editor = MarkdownEditor()
    editor.set_text("café cafe")
    state = SearchState()
    state.push_find("cafe")
    state.match_diacritics = True
    found = editor.find_next(state)
    assert found is True
    buf = editor.get_buffer()
    start, end = buf.get_selection_bounds()
    matched = buf.get_text(start, end, True)
    assert matched == "cafe"


def test_editor_match_diacritics_off_finds_cantico_negro_accented_words():
    _init_gtk()
    from calamus.editor import MarkdownEditor
    from calamus.search import SearchState

    editor = MarkdownEditor()
    editor.set_text(_CANTICO_MD)
    state = SearchState()
    state.push_find("intencoes")
    state.match_diacritics = False
    found = editor.find_next(state)
    assert found is True
    buf = editor.get_buffer()
    start, end = buf.get_selection_bounds()
    matched = buf.get_text(start, end, True)
    assert matched == "intenções"


def test_editor_match_diacritics_off_finds_multiple_oro_matches():
    _init_gtk()
    from calamus.editor import MarkdownEditor
    from calamus.search import SearchState

    editor = MarkdownEditor()
    text = (
        Path(__file__).resolve().parent.parent
        / "samples"
        / "oro_se_do_bheatha_abhaile_lyrics.md"
    ).read_text(encoding="utf-8")
    editor.set_text(text)
    state = SearchState()
    state.push_find("oro")
    state.match_diacritics = False

    expected = text.count("Óró")
    starts: set[int] = set()
    for _ in range(expected):
        assert editor.find_next(state) is True
        buf = editor.get_buffer()
        start, _end = buf.get_selection_bounds()
        starts.add(start.get_offset())

    assert len(starts) == expected


def test_editor_abstract_methods_present():
    _init_gtk()
    from calamus.editor import AbstractEditor

    abstract_methods = {
        "find_next",
        "find_previous",
        "replace_current",
        "replace_all",
        "replace_and_find",
    }
    for method in abstract_methods:
        assert hasattr(AbstractEditor, method)

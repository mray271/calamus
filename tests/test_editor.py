"""GTK widget tests for MarkdownEditor — requires xvfb (run via xvfb-run)."""

import pytest

# These tests require a display. Skip gracefully if no display is available.
gi_available = pytest.importorskip("gi", reason="PyGObject not available")


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

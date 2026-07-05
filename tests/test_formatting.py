"""Unit tests for calamus.formatting helpers."""

import pytest


class FakeBuffer:
    def __init__(self, text="", selection=None):
        self._text = text
        self._selection = selection
        self._has_selection = selection is not None

    def get_has_selection(self):
        return self._has_selection

    def get_selection_bounds(self):
        return FakeIter(self, *self._selection), FakeIter(self, *self._selection)

    def get_text(self, start, end, include_hidden):
        if self._selection:
            return self._text[self._selection[0] : self._selection[1]]
        return self._text

    def begin_user_action(self):
        pass

    def end_user_action(self):
        pass

    def delete_selection(self, interactive, default):
        if self._selection:
            self._text = (
                self._text[: self._selection[0]] + self._text[self._selection[1] :]
            )
            self._selection = None
            self._has_selection = False

    def insert_at_cursor(self, text):
        self._text += text

    def get_insert(self):
        return None

    def get_iter_at_mark(self, mark):
        return FakeIter(self, 0, len(self._text))

    def place_cursor(self, it):
        pass


class FakeIter:
    def __init__(self, buf, start, end=None):
        self._buf = buf
        self._start = start
        self._end = end if end is not None else start

    def set_line_offset(self, offset):
        pass


class FakeEditor:
    def __init__(self, text="", selection=None):
        self._buf = FakeBuffer(text, selection)
        self._inserted = []

    def get_buffer(self):
        return self._buf

    def get_selection(self):
        if self._buf._selection:
            s, e = self._buf._selection
            return self._buf._text[s:e], True
        return "", False

    def replace_selection(self, new_text):
        self._inserted.append(("replace", new_text))

    def insert_at_cursor(self, text):
        self._inserted.append(("insert", text))


def test_apply_bold_with_selection():
    from calamus.formatting import BoldAction

    editor = FakeEditor("hello world", selection=(6, 11))
    BoldAction().apply(editor)
    assert editor._inserted == [("replace", "**world**")]


def test_apply_bold_no_selection():
    from calamus.formatting import BoldAction

    editor = FakeEditor()
    BoldAction().apply(editor)
    assert any("**text**" in str(item) for item in editor._inserted)


def test_apply_italic_with_selection():
    from calamus.formatting import ItalicAction

    editor = FakeEditor("hello", selection=(0, 5))
    ItalicAction().apply(editor)
    assert editor._inserted == [("replace", "*hello*")]


def test_apply_heading():
    from calamus.formatting import HeadingAction

    editor = FakeEditor()
    HeadingAction(2).apply(editor)
    assert any("## " in str(item) for item in editor._inserted)


def test_apply_code_block_with_selection():
    from calamus.formatting import CodeBlockAction

    editor = FakeEditor("print('hi')", selection=(0, 11))
    CodeBlockAction().apply(editor)
    assert editor._inserted == [("replace", "```\nprint('hi')\n```")]


def test_apply_unordered_list_no_selection():
    from calamus.formatting import UnorderedListAction

    editor = FakeEditor()
    UnorderedListAction().apply(editor)
    assert any("- " in str(item) for item in editor._inserted)


def test_apply_ordered_list_with_selection():
    from calamus.formatting import OrderedListAction

    editor = FakeEditor("item one\nitem two", selection=(0, 17))
    OrderedListAction().apply(editor)
    assert editor._inserted == [("replace", "1. item one\n2. item two")]


def test_apply_horizontal_rule():
    from calamus.formatting import HorizontalRuleAction

    editor = FakeEditor()
    HorizontalRuleAction().apply(editor)
    assert any("---" in str(item) for item in editor._inserted)


def test_apply_strikethrough():
    from calamus.formatting import StrikethroughAction

    editor = FakeEditor("delete me", selection=(0, 9))
    StrikethroughAction().apply(editor)
    assert editor._inserted == [("replace", "~~delete me~~")]


def test_apply_blockquote_with_selection():
    from calamus.formatting import BlockquoteAction

    editor = FakeEditor("line one\nline two", selection=(0, 17))
    BlockquoteAction().apply(editor)
    assert editor._inserted == [("replace", "> line one\n> line two")]


def test_bold_action_name():
    from calamus.formatting import BoldAction

    assert BoldAction().action_name == "fmt-bold"


def test_italic_action_apply():
    from calamus.formatting import ItalicAction

    editor = FakeEditor("hello", selection=(0, 5))
    ItalicAction().apply(editor)
    assert editor._inserted == [("replace", "*hello*")]


def test_formatting_registry_contains_all_actions():
    from calamus.formatting import FormattingRegistry

    actions = FormattingRegistry.get_all()
    names = [action.action_name for action in actions]
    assert "fmt-bold" in names
    assert "fmt-italic" in names
    assert "fmt-h1" in names
    assert "fmt-code-block" in names
    assert "fmt-link" in names


def test_formatting_registry_lookup():
    from calamus.formatting import FormattingRegistry

    action = FormattingRegistry.get_by_action_name("fmt-bold")
    assert action is not None
    assert action.name == "Bold"


# ---------------------------------------------------------------------------
# All heading levels
# ---------------------------------------------------------------------------


def test_heading_action_all_levels():
    from calamus.formatting import HeadingAction

    for level in range(1, 7):
        editor = FakeEditor()
        HeadingAction(level).apply(editor)
        prefix = "#" * level + " "
        assert any(prefix in str(item) for item in editor._inserted)


def test_heading_action_names():
    from calamus.formatting import HeadingAction

    for level in range(1, 7):
        action = HeadingAction(level)
        assert action.action_name == f"fmt-h{level}"
        assert str(level) in action.name


# ---------------------------------------------------------------------------
# Inline actions
# ---------------------------------------------------------------------------


def test_bold_italic_action():
    from calamus.formatting import BoldItalicAction

    editor = FakeEditor("text", selection=(0, 4))
    BoldItalicAction().apply(editor)
    assert editor._inserted == [("replace", "***text***")]


def test_bold_italic_action_name():
    from calamus.formatting import BoldItalicAction

    assert BoldItalicAction().action_name == "fmt-bold-italic"


def test_inline_code_action_with_selection():
    from calamus.formatting import InlineCodeAction

    editor = FakeEditor("var", selection=(0, 3))
    InlineCodeAction().apply(editor)
    assert editor._inserted == [("replace", "`var`")]


def test_inline_code_action_no_selection():
    from calamus.formatting import InlineCodeAction

    editor = FakeEditor()
    InlineCodeAction().apply(editor)
    assert any("`" in str(item) for item in editor._inserted)


def test_inline_code_action_name():
    from calamus.formatting import InlineCodeAction

    assert InlineCodeAction().action_name == "fmt-inline-code"


def test_strikethrough_action_name():
    from calamus.formatting import StrikethroughAction

    assert StrikethroughAction().action_name == "fmt-strikethrough"


# ---------------------------------------------------------------------------
# Line actions
# ---------------------------------------------------------------------------


def test_blockquote_action_name():
    from calamus.formatting import BlockquoteAction

    assert BlockquoteAction().action_name == "fmt-blockquote"


def test_ordered_list_action_name():
    from calamus.formatting import OrderedListAction

    assert OrderedListAction().action_name == "fmt-ordered-list"


def test_unordered_list_action_name():
    from calamus.formatting import UnorderedListAction

    assert UnorderedListAction().action_name == "fmt-unordered-list"


def test_unordered_list_with_selection():
    from calamus.formatting import UnorderedListAction

    editor = FakeEditor("line one\nline two", selection=(0, 17))
    UnorderedListAction().apply(editor)
    assert editor._inserted == [("replace", "- line one\n- line two")]


# ---------------------------------------------------------------------------
# Block actions
# ---------------------------------------------------------------------------


def test_code_block_action_no_selection():
    from calamus.formatting import CodeBlockAction

    editor = FakeEditor()
    CodeBlockAction().apply(editor)
    assert any("```" in str(item) for item in editor._inserted)


def test_code_block_action_name():
    from calamus.formatting import CodeBlockAction

    assert CodeBlockAction().action_name == "fmt-code-block"


def test_horizontal_rule_action_name():
    from calamus.formatting import HorizontalRuleAction

    assert HorizontalRuleAction().action_name == "fmt-horizontal-rule"


# ---------------------------------------------------------------------------
# FormattingRegistry completeness
# ---------------------------------------------------------------------------


def test_registry_returns_unique_action_names():
    from calamus.formatting import FormattingRegistry

    names = [a.action_name for a in FormattingRegistry.get_all()]
    assert len(names) == len(set(names)), "Duplicate action names in registry"


def test_registry_miss_returns_none():
    from calamus.formatting import FormattingRegistry

    assert FormattingRegistry.get_by_action_name("fmt-does-not-exist") is None


def test_registry_has_all_heading_levels():
    from calamus.formatting import FormattingRegistry

    names = [a.action_name for a in FormattingRegistry.get_all()]
    for level in range(1, 7):
        assert f"fmt-h{level}" in names


def test_registry_has_link_and_image():
    from calamus.formatting import FormattingRegistry

    names = [a.action_name for a in FormattingRegistry.get_all()]
    assert "fmt-link" in names
    assert "fmt-image" in names


def test_all_actions_have_non_empty_name_and_action_name():
    from calamus.formatting import FormattingRegistry

    for action in FormattingRegistry.get_all():
        assert action.name, f"{type(action).__name__}.name is empty"
        assert action.action_name, f"{type(action).__name__}.action_name is empty"
        assert action.action_name.startswith("fmt-")

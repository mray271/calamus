"""Class-based Markdown formatting actions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from calamus.editor import AbstractEditor


class AbstractFormattingAction(ABC):
    """Base interface for formatting actions."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable action name."""

    @property
    @abstractmethod
    def action_name(self) -> str:
        """GAction identifier for the action."""

    @abstractmethod
    def apply(self, editor: AbstractEditor) -> None:
        """Apply formatting to the given editor."""


class InlineFormattingAction(AbstractFormattingAction, ABC):
    """Formatting action that wraps the selection."""

    prefix: ClassVar[str] = ""
    suffix: ClassVar[str] = ""
    placeholder: ClassVar[str] = "text"

    def apply(self, editor: AbstractEditor) -> None:
        text, has_selection = editor.get_selection()
        content = text if has_selection else self.placeholder
        wrapped = f"{self.prefix}{content}{self.suffix}"
        if has_selection:
            editor.replace_selection(wrapped)
        else:
            editor.insert_at_cursor(wrapped)


class BoldAction(InlineFormattingAction):
    prefix = "**"
    suffix = "**"

    @property
    def name(self) -> str:
        return "Bold"

    @property
    def action_name(self) -> str:
        return "fmt-bold"


class ItalicAction(InlineFormattingAction):
    prefix = "*"
    suffix = "*"

    @property
    def name(self) -> str:
        return "Italic"

    @property
    def action_name(self) -> str:
        return "fmt-italic"


class BoldItalicAction(InlineFormattingAction):
    prefix = "***"
    suffix = "***"

    @property
    def name(self) -> str:
        return "Bold & Italic"

    @property
    def action_name(self) -> str:
        return "fmt-bold-italic"


class StrikethroughAction(InlineFormattingAction):
    prefix = "~~"
    suffix = "~~"

    @property
    def name(self) -> str:
        return "Strikethrough"

    @property
    def action_name(self) -> str:
        return "fmt-strikethrough"


class InlineCodeAction(InlineFormattingAction):
    prefix = "`"
    suffix = "`"

    @property
    def name(self) -> str:
        return "Inline Code"

    @property
    def action_name(self) -> str:
        return "fmt-inline-code"


class LineFormattingAction(AbstractFormattingAction, ABC):
    """Formatting action that prefixes lines."""

    prefix: ClassVar[str] = ""

    def apply(self, editor: AbstractEditor) -> None:
        text, has_selection = editor.get_selection()
        if has_selection:
            lines = text.split("\n")
            editor.replace_selection(self._format_lines(lines))
            return
        buffer = editor.get_buffer()
        iterator = buffer.get_iter_at_mark(buffer.get_insert())
        iterator.set_line_offset(0)
        buffer.place_cursor(iterator)
        editor.insert_at_cursor(self.prefix)

    def _format_lines(self, lines: list[str]) -> str:
        return "\n".join(f"{self.prefix}{line}" for line in lines)


class HeadingAction(LineFormattingAction):
    def __init__(self, level: int) -> None:
        self._level = level
        self.prefix = "#" * level + " "

    @property
    def name(self) -> str:
        return f"Heading {self._level}"

    @property
    def action_name(self) -> str:
        return f"fmt-h{self._level}"


class BlockquoteAction(LineFormattingAction):
    prefix = "> "

    @property
    def name(self) -> str:
        return "Blockquote"

    @property
    def action_name(self) -> str:
        return "fmt-blockquote"


class OrderedListAction(LineFormattingAction):
    @property
    def name(self) -> str:
        return "Ordered List"

    @property
    def action_name(self) -> str:
        return "fmt-ordered-list"

    def _format_lines(self, lines: list[str]) -> str:
        return "\n".join(f"{index + 1}. {line}" for index, line in enumerate(lines))

    def apply(self, editor: AbstractEditor) -> None:
        text, has_selection = editor.get_selection()
        if has_selection:
            editor.replace_selection(self._format_lines(text.split("\n")))
        else:
            editor.insert_at_cursor("1. ")


class UnorderedListAction(LineFormattingAction):
    prefix = "- "

    @property
    def name(self) -> str:
        return "Unordered List"

    @property
    def action_name(self) -> str:
        return "fmt-unordered-list"


class BlockFormattingAction(AbstractFormattingAction, ABC):
    """Formatting action that inserts block content."""


class CodeBlockAction(BlockFormattingAction):
    @property
    def name(self) -> str:
        return "Code Block"

    @property
    def action_name(self) -> str:
        return "fmt-code-block"

    def apply(self, editor: AbstractEditor) -> None:
        text, has_selection = editor.get_selection()
        if has_selection:
            editor.replace_selection(f"```\n{text}\n```")
        else:
            editor.insert_at_cursor("```\ncode here\n```")


class HorizontalRuleAction(BlockFormattingAction):
    @property
    def name(self) -> str:
        return "Horizontal Rule"

    @property
    def action_name(self) -> str:
        return "fmt-horizontal-rule"

    def apply(self, editor: AbstractEditor) -> None:
        editor.insert_at_cursor("\n---\n")


class DialogFormattingAction(AbstractFormattingAction, ABC):
    """Formatting action that requires a parent window."""

    def __init__(self, parent: Gtk.Window | None = None) -> None:
        self._parent = parent

    def set_parent(self, parent: Gtk.Window) -> None:
        self._parent = parent

    def _require_parent(self) -> Gtk.Window | None:
        return self._parent


class LinkAction(DialogFormattingAction):
    @property
    def name(self) -> str:
        return "Link"

    @property
    def action_name(self) -> str:
        return "fmt-link"

    def apply(self, editor: AbstractEditor) -> None:
        parent = self._require_parent()
        if parent is None:
            return
        text, has_selection = editor.get_selection()
        dialog = Adw.MessageDialog.new(parent, "Insert Link", None)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("insert", "Insert")
        dialog.set_default_response("insert")
        dialog.set_close_response("cancel")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        url_entry = Gtk.Entry()
        url_entry.set_placeholder_text("https://example.com")
        text_entry = Gtk.Entry()
        text_entry.set_placeholder_text("Link text")
        text_entry.set_text(text if has_selection else "")
        box.append(Gtk.Label(label="URL:"))
        box.append(url_entry)
        box.append(Gtk.Label(label="Text:"))
        box.append(text_entry)
        dialog.set_extra_child(box)

        def on_response(_dialog: Adw.MessageDialog, response: str) -> None:
            if response != "insert":
                return
            url = url_entry.get_text() or "url"
            link_text = text_entry.get_text() or "link"
            result = f"[{link_text}]({url})"
            if has_selection:
                editor.replace_selection(result)
            else:
                editor.insert_at_cursor(result)

        dialog.connect("response", on_response)
        dialog.present()


class ImageAction(DialogFormattingAction):
    @property
    def name(self) -> str:
        return "Image"

    @property
    def action_name(self) -> str:
        return "fmt-image"

    def apply(self, editor: AbstractEditor) -> None:
        parent = self._require_parent()
        if parent is None:
            return
        dialog = Adw.MessageDialog.new(parent, "Insert Image", None)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("insert", "Insert")
        dialog.set_default_response("insert")
        dialog.set_close_response("cancel")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        url_entry = Gtk.Entry()
        url_entry.set_placeholder_text("https://example.com/image.png")
        alt_entry = Gtk.Entry()
        alt_entry.set_placeholder_text("Alt text")
        box.append(Gtk.Label(label="Image URL:"))
        box.append(url_entry)
        box.append(Gtk.Label(label="Alt text:"))
        box.append(alt_entry)
        dialog.set_extra_child(box)

        def on_response(_dialog: Adw.MessageDialog, response: str) -> None:
            if response != "insert":
                return
            url = url_entry.get_text() or "image.png"
            alt = alt_entry.get_text() or "image"
            editor.insert_at_cursor(f"![{alt}]({url})")

        dialog.connect("response", on_response)
        dialog.present()


class FormattingRegistry:
    """Registry for all formatting actions."""

    _actions: ClassVar[list[AbstractFormattingAction]] = [
        HeadingAction(1),
        HeadingAction(2),
        HeadingAction(3),
        HeadingAction(4),
        HeadingAction(5),
        HeadingAction(6),
        BoldAction(),
        ItalicAction(),
        BoldItalicAction(),
        StrikethroughAction(),
        InlineCodeAction(),
        CodeBlockAction(),
        BlockquoteAction(),
        OrderedListAction(),
        UnorderedListAction(),
        HorizontalRuleAction(),
        LinkAction(),
        ImageAction(),
    ]

    @classmethod
    def get_all(cls) -> list[AbstractFormattingAction]:
        return list(cls._actions)

    @classmethod
    def get_by_action_name(cls, name: str) -> AbstractFormattingAction | None:
        for action in cls._actions:
            if action.action_name == name:
                return action
        return None

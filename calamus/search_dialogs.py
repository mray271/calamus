"""GTK dialog implementations for Find and Replace.

This module contains ``FindDialog`` and ``ReplaceDialog``, which are Adw.Window
subclasses that require a running GtkApplication.  It is intentionally excluded
from the coverage report (see ``pyproject.toml``).

Pure-Python handler logic lives in :mod:`calamus.search`
(``FindDialogLogic`` / ``ReplaceDialogLogic``) and is unit-tested there.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from calamus.search import (
    FindDialogLogic,
    ReplaceDialogLogic,
    SearchState,
)

if TYPE_CHECKING:
    from calamus.editor import AbstractEditor


# ---------------------------------------------------------------------------
# Goto Line dialog
# ---------------------------------------------------------------------------


class GotoLineDialog(Adw.Window):
    """A non-modal Go to Line / Column dialog.

    Accepts ``line`` or ``line:column`` input, jumps to that position in
    *editor*, and selects the entire target line.
    """

    def __init__(self, editor: "AbstractEditor", parent: Gtk.Window) -> None:
        super().__init__()
        self._editor = editor
        self.set_title("Go to Line")
        self.set_default_size(300, -1)
        self.set_resizable(True)
        self.set_modal(False)
        self.set_transient_for(parent)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(16)
        box.set_margin_end(16)

        entry = Gtk.Entry()
        entry.set_placeholder_text("line[:column]")
        box.append(entry)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _b: self.close())
        ok_btn = Gtk.Button(label="Go")
        ok_btn.add_css_class("suggested-action")
        btn_box.append(cancel_btn)
        btn_box.append(ok_btn)
        box.append(btn_box)

        toolbar_view.set_content(box)
        self.set_content(toolbar_view)

        ok_btn.connect("clicked", lambda _b: self._go(entry))
        entry.connect("activate", lambda _e: self._go(entry))

        self.present()

    def _go(self, entry: Gtk.Entry) -> None:
        text = entry.get_text().strip()
        parts = text.split(":", 1)
        try:
            line = int(parts[0]) - 1
        except ValueError:
            return
        col = 0
        if len(parts) == 2:
            try:
                col = max(0, int(parts[1]) - 1)
            except ValueError:
                col = 0
        self._editor.goto_line(max(0, line), col)
        self.close()


# ---------------------------------------------------------------------------
# GTK helper functions
# ---------------------------------------------------------------------------


def _build_options_box(
    state: SearchState,
) -> tuple[Gtk.Box, dict[str, Gtk.CheckButton]]:
    """Build the five option CheckButtons shared by Find and Replace dialogs.

    Laid out in two horizontal rows to save vertical space:
      Row 1: Regular Expression, Case Sensitive, Whole Word
      Row 2: Search Backward, Keep Dialog
    """
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    outer.append(row1)
    outer.append(row2)

    checks: dict[str, Gtk.CheckButton] = {}
    rows = {
        "use_regex": row1,
        "case_sensitive": row1,
        "whole_word": row1,
        "search_backward": row2,
        "keep_dialog": row2,
    }
    for key, label in [
        ("use_regex", "Regular Expression"),
        ("case_sensitive", "Case Sensitive"),
        ("whole_word", "Whole Word"),
        ("search_backward", "Search Backward"),
        ("keep_dialog", "Keep Dialog"),
    ]:
        btn = Gtk.CheckButton(label=label)
        btn.set_active(getattr(state, key))
        rows[key].append(btn)
        checks[key] = btn
    return outer, checks


def _wire_regex_constraints(checks: dict[str, Gtk.CheckButton]) -> None:
    """Wire the "Regular Expression" checkbox side-effects.

    When regex is toggled on:
      - "Case Sensitive" is set to True.
      - "Whole Word" is deactivated (insensitive) regardless of its state.
    When regex is toggled off:
      - "Whole Word" becomes interactive again.
    """
    regex_btn = checks["use_regex"]
    case_btn = checks["case_sensitive"]
    whole_word_btn = checks["whole_word"]

    def _on_regex_toggled(btn: Gtk.CheckButton) -> None:
        if btn.get_active():
            case_btn.set_active(True)
            whole_word_btn.set_sensitive(False)
        else:
            whole_word_btn.set_sensitive(True)

    # Apply initial state if regex is already on.
    _on_regex_toggled(regex_btn)
    regex_btn.connect("toggled", _on_regex_toggled)


def _wire_entry_history_recall(
    entry: Gtk.Entry,
    prev_fn: Callable[[], str | None],
    next_fn: Callable[[], str | None],
) -> None:
    """Wire ↑/↓ key-press events on *entry* for history recall.

    *prev_fn* is called on ↑ (older), *next_fn* on ↓ (newer).
    Both should return the text to set, or ``None`` to leave the entry unchanged / clear it.
    """
    key_controller = Gtk.EventControllerKey.new()

    def on_key_pressed(
        _ctrl: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _modifiers: int,
    ) -> bool:
        from gi.repository import Gdk

        if keyval == Gdk.KEY_Up:
            value = prev_fn()
            if value is not None:
                entry.set_text(value)
                entry.set_position(-1)
            return True
        if keyval == Gdk.KEY_Down:
            value = next_fn()
            entry.set_text(value if value is not None else "")
            entry.set_position(-1)
            return True
        return False

    key_controller.connect("key-pressed", on_key_pressed)
    entry.add_controller(key_controller)


def _wire_keep_dialog_title(
    dialog: Adw.Window,
    base_title: str,
    checks: dict[str, Gtk.CheckButton],
    file_path: str | None,
) -> None:
    """Update the dialog title based on the 'Keep Dialog' checkbox state.

    When 'Keep Dialog' is active the title becomes
    "<base_title> (in <filename>)" where *filename* is the basename of
    *file_path*.  When it is inactive the title reverts to *base_title*.
    """
    import os

    keep_btn = checks["keep_dialog"]
    filename = os.path.basename(file_path) if file_path else None

    def _update_title(btn: Gtk.CheckButton) -> None:
        if btn.get_active() and filename:
            dialog.set_title(f"{base_title} (in {filename})")
        else:
            dialog.set_title(base_title)

    _update_title(keep_btn)
    keep_btn.connect("toggled", _update_title)


class FindDialog(FindDialogLogic, Adw.Window):
    """A non-modal Find dialog with options and history recall."""

    def __init__(
        self,
        editor: AbstractEditor,
        state: SearchState,
        file_path: str | None = None,
        **kwargs: object,
    ) -> None:
        Adw.Window.__init__(self, **kwargs)
        self._editor = editor
        # _live_state is the window's shared state (used by Find Again etc.).
        # _state is a fresh blank scratch copy for this dialog session.
        # History lists are shared by reference so ↑/↓ recall works.
        self._live_state = state
        self._state = state.make_dialog_scratch()
        self.set_title("Find")
        self.set_modal(False)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.set_margin_start(16)
        content_box.set_margin_end(16)

        find_label = Gtk.Label(
            label="String to Find  (use ↑ arrow key to recall previous)", xalign=0.0
        )
        content_box.append(find_label)
        self._find_entry = Gtk.Entry()
        self._find_entry.set_hexpand(True)
        # Scratch state is blank — entry starts empty.
        # ↑/↓ history recall pulls from the shared live history list.
        _wire_entry_history_recall(
            self._find_entry, self._state.history_prev, self._state.history_next
        )
        content_box.append(self._find_entry)

        options_box, self._checks = _build_options_box(self._state)
        _wire_regex_constraints(self._checks)
        _wire_keep_dialog_title(self, "Find", self._checks, file_path)
        content_box.append(options_box)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _b: self.close())
        find_btn = Gtk.Button(label="Find")
        find_btn.add_css_class("suggested-action")
        find_btn.connect("clicked", lambda _b: self.handle_find())
        btn_box.append(cancel_btn)
        btn_box.append(find_btn)
        content_box.append(btn_box)

        toolbar_view.set_content(content_box)
        self.set_content(toolbar_view)

        def _update_find_sensitivity(*_: object) -> None:
            has_text = bool(self._find_entry.get_text())
            find_btn.set_sensitive(has_text)

        _update_find_sensitivity()
        self._find_entry.connect("notify::text", _update_find_sensitivity)
        # No close-request hook: Cancel and window-close leave live state
        # untouched so Find Again continues using the prior search settings.

    def get_find_text(self) -> str:
        return self._find_entry.get_text()

    def close_dialog(self) -> None:
        self.close()


class ReplaceDialog(ReplaceDialogLogic, Adw.Window):
    """A non-modal Replace dialog with options, history recall, and scope buttons."""

    def __init__(
        self,
        editor: AbstractEditor,
        state: SearchState,
        tab_manager: object = None,
        file_path: str | None = None,
        **kwargs: object,
    ) -> None:
        Adw.Window.__init__(self, **kwargs)
        self._editor = editor
        # _live_state is the window's shared state (used by Replace Again etc.).
        # _state is a fresh blank scratch copy for this dialog session.
        # History lists are shared by reference so ↑/↓ recall works.
        self._live_state = state
        self._state = state.make_dialog_scratch()
        self._tab_manager = tab_manager
        self.set_title("Replace/Find")
        self.set_modal(False)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.set_margin_start(16)
        content_box.set_margin_end(16)

        find_label = Gtk.Label(
            label="String to Find  (use ↑ arrow key to recall previous)", xalign=0.0
        )
        content_box.append(find_label)
        self._find_entry = Gtk.Entry()
        self._find_entry.set_hexpand(True)
        # Scratch state is blank — entries start empty.
        # ↑/↓ history recall pulls from the shared live history list.
        _wire_entry_history_recall(
            self._find_entry, self._state.history_prev, self._state.history_next
        )
        content_box.append(self._find_entry)

        replace_label = Gtk.Label(
            label="Replace With  (use ↑ arrow key to recall previous)", xalign=0.0
        )
        content_box.append(replace_label)
        self._replace_entry = Gtk.Entry()
        self._replace_entry.set_hexpand(True)
        _wire_entry_history_recall(
            self._replace_entry,
            self._state.replace_history_prev,
            self._state.replace_history_next,
        )
        content_box.append(self._replace_entry)

        options_box, self._checks = _build_options_box(self._state)
        _wire_regex_constraints(self._checks)
        _wire_keep_dialog_title(self, "Replace/Find", self._checks, file_path)
        content_box.append(options_box)

        replace_all_label = Gtk.Label(label="Replace all in:", xalign=0.0)
        content_box.append(replace_all_label)
        scope_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        scope_btns: list[Gtk.Button] = []
        for scope_label, scope_key in [
            ("Window", "window"),
            ("Selection", "selection"),
            ("Multiple Tabs/Documents", "all_tabs"),
        ]:
            btn = Gtk.Button(label=scope_label)
            btn.connect("clicked", lambda _b, sk=scope_key: self.handle_replace_all(sk))
            scope_box.append(btn)
            scope_btns.append(btn)
        content_box.append(scope_box)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        action_btns: list[Gtk.Button] = []
        for label, callback in [
            ("Cancel", lambda _b: self.close()),
            ("Find", lambda _b: self.handle_find()),
            ("Replace", lambda _b: self.handle_replace()),
            ("Replace & Find", lambda _b: self.handle_replace_and_find()),
        ]:
            btn = Gtk.Button(label=label)
            btn.connect("clicked", callback)
            if label == "Replace & Find":
                btn.add_css_class("suggested-action")
            btn_box.append(btn)
            if label != "Cancel":
                action_btns.append(btn)
        content_box.append(btn_box)

        toolbar_view.set_content(content_box)
        self.set_content(toolbar_view)

        def _update_replace_sensitivity(*_: object) -> None:
            has_text = bool(self._find_entry.get_text())
            for b in action_btns + scope_btns:
                b.set_sensitive(has_text)

        _update_replace_sensitivity()
        self._find_entry.connect("notify::text", _update_replace_sensitivity)
        # No close-request hook: Cancel and window-close leave live state
        # untouched so Replace Again continues using the prior settings.

    def get_find_text(self) -> str:
        return self._find_entry.get_text()

    def get_replace_text(self) -> str:
        return self._replace_entry.get_text()

    def close_dialog(self) -> None:
        self.close()

    def _show_replace_all_result(self, count: int) -> None:
        msg = f"Replaced {count} occurrence{'s' if count != 1 else ''}."
        toast = Adw.Toast.new(msg)
        toast.set_timeout(3)
        # Walk the transient-for parent's widget tree to find the ToastOverlay.
        parent = self.get_transient_for()
        widget: Gtk.Widget | None = parent.get_child() if parent else None
        while widget is not None:
            if isinstance(widget, Adw.ToastOverlay):
                widget.add_toast(toast)
                return
            widget = widget.get_first_child()

"""Search/replace state, logic mixins, and supporting data structures."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from calamus.editor import AbstractEditor
    from calamus.protocols import HasGetActive
    from calamus.tabs import AbstractTabManager

_MAX_HISTORY = 20


@dataclass
class SearchState:
    """Shared state for all find/replace operations and dialogs.

    A single instance (``_search_state``) is owned by CalamusWindow and
    represents the **active** settings used by Find Again, Find Again Reverse,
    Replace and Find Again, and Replace Again.  It starts empty and is only
    updated when the user clicks an action button in a dialog.

    Dialogs always open fresh (empty entries, all options unchecked) and
    operate on a local scratch copy.  On action the scratch copy is committed
    to the live instance.  Cancel / close never touches the live instance.

    History (``find_history``, ``replace_history``) lives on the live instance
    and is shared with dialog scratch copies by reference so that ↑/↓ recall
    always reflects the full accumulated history even in fresh dialogs.
    """

    find_history: list[str] = field(default_factory=list)
    replace_string: str = ""
    replace_history: list[str] = field(default_factory=list)
    use_regex: bool = False
    case_sensitive: bool = False
    whole_word: bool = False
    search_backward: bool = False
    keep_dialog: bool = False

    # Internal pointers used by up-arrow history recall in dialogs.
    _history_index: int = field(default=-1, repr=False)
    _replace_history_index: int = field(default=-1, repr=False)

    # ---------------------------------------------------------------------------
    # History helpers
    # ---------------------------------------------------------------------------

    def push_find(self, text: str) -> None:
        """Record a search string in history (deduplicates, most-recent last)."""
        if not text:
            return
        if text in self.find_history:
            self.find_history.remove(text)
        self.find_history.append(text)
        if len(self.find_history) > _MAX_HISTORY:
            self.find_history.pop(0)
        self._history_index = -1

    def push_replace(self, text: str) -> None:
        """Record a replace string in history (deduplicates, most-recent last)."""
        if not text:
            return
        if text in self.replace_history:
            self.replace_history.remove(text)
        self.replace_history.append(text)
        if len(self.replace_history) > _MAX_HISTORY:
            self.replace_history.pop(0)
        self._replace_history_index = -1

    def history_prev(self) -> str | None:
        """Return the previous history entry (up-arrow), or None if exhausted."""
        if not self.find_history:
            return None
        if self._history_index == -1:
            self._history_index = len(self.find_history) - 1
        elif self._history_index > 0:
            self._history_index -= 1
        return self.find_history[self._history_index]

    def history_next(self) -> str | None:
        """Return the next history entry (down-arrow), or None if at the end."""
        if not self.find_history or self._history_index == -1:
            return None
        if self._history_index < len(self.find_history) - 1:
            self._history_index += 1
            return self.find_history[self._history_index]
        self._history_index = -1
        return None

    def replace_history_prev(self) -> str | None:
        """Return the previous replace history entry (up-arrow)."""
        if not self.replace_history:
            return None
        if self._replace_history_index == -1:
            self._replace_history_index = len(self.replace_history) - 1
        elif self._replace_history_index > 0:
            self._replace_history_index -= 1
        return self.replace_history[self._replace_history_index]

    def replace_history_next(self) -> str | None:
        """Return the next replace history entry (down-arrow)."""
        if not self.replace_history or self._replace_history_index == -1:
            return None
        if self._replace_history_index < len(self.replace_history) - 1:
            self._replace_history_index += 1
            return self.replace_history[self._replace_history_index]
        self._replace_history_index = -1
        return None

    def reset_history_cursor(self) -> None:
        """Reset history navigation indices (call when dialog opens fresh)."""
        self._history_index = -1
        self._replace_history_index = -1

    def make_dialog_scratch(self) -> "SearchState":
        """Return a fresh blank SearchState for dialog-local use.

        All option flags start at their defaults (False) and entries are
        empty, so dialogs always open clean.  The new instance shares the
        same ``find_history`` and ``replace_history`` list objects as the
        live state so that ↑/↓ recall in the dialog reflects the full
        accumulated history.
        """
        scratch = SearchState(
            find_history=self.find_history,
            replace_history=self.replace_history,
        )
        return scratch

    def commit_to(self, target: "SearchState") -> None:
        """Copy this state's options and strings into *target* (the live state).

        Called when the user clicks an action button so that Find Again and
        Replace Again pick up the new settings.  History lists are already
        shared by reference and updated in place via push_find/push_replace,
        so they do not need to be copied.
        """
        target.find_history[:] = self.find_history
        target.replace_history[:] = self.replace_history
        target.replace_string = self.replace_string
        target.use_regex = self.use_regex
        target.case_sensitive = self.case_sensitive
        target.whole_word = self.whole_word
        target.search_backward = self.search_backward
        target.keep_dialog = self.keep_dialog


# ---------------------------------------------------------------------------
# Dialog helpers
# ---------------------------------------------------------------------------


def _sync_options_to_state(
    checks: "dict[str, HasGetActive]", state: SearchState
) -> None:
    """Copy checkbox states into *state*.

    *checks* maps option-key strings to objects with a ``get_active()`` method
    (e.g. ``Gtk.CheckButton``).
    """
    for key, btn in checks.items():
        setattr(state, key, btn.get_active())


class FindDialogLogic:
    """Pure-Python handler logic for the Find dialog.

    Subclassed by ``FindDialog`` (GTK) and used directly in tests.
    Subclasses must implement :meth:`get_find_text`; override
    :meth:`close_dialog` to actually dismiss a window.

    ``_state`` is a dialog-local scratch copy (always fresh/blank on open).
    ``_live_state`` is the window's shared state used by Find Again etc.
    Action buttons sync scratch → live; Cancel/close leaves live untouched.

    Note: intentionally does *not* inherit ``ABC`` — mixing ABCMeta with
    GObject's metaclass causes a metaclass conflict in GTK subclasses.
    The ``@abstractmethod`` markers are enforced statically by type checkers.
    """

    _editor: "AbstractEditor"
    _state: SearchState  # dialog-local scratch copy
    _live_state: SearchState  # window's shared live state
    _checks: "dict[str, HasGetActive]"

    @abstractmethod
    def get_find_text(self) -> str:
        """Return the current text in the find entry."""

    def close_dialog(self) -> None:
        """Close the dialog. No-op in pure-logic / test context."""

    def handle_find(self) -> bool:
        """Commit scratch state to live state and execute find.

        Returns True if a match was found.
        """
        text = self.get_find_text()
        _sync_options_to_state(self._checks, self._state)
        self._state.push_find(text)
        self._state.commit_to(self._live_state)
        if self._live_state.search_backward:
            found = self._editor.find_previous(self._live_state)
        else:
            found = self._editor.find_next(self._live_state)
        if found and not self._live_state.keep_dialog:
            self.close_dialog()
        return found


class ReplaceDialogLogic:
    """Pure-Python handler logic for the Replace dialog.

    Subclassed by ``ReplaceDialog`` (GTK) and used directly in tests.
    Subclasses must implement :meth:`get_find_text` and
    :meth:`get_replace_text`; override :meth:`close_dialog` to dismiss a window.

    ``_state`` is a dialog-local scratch copy (always fresh/blank on open).
    ``_live_state`` is the window's shared state used by Replace Again etc.
    Action buttons sync scratch → live; Cancel/close leaves live untouched.

    Note: intentionally does *not* inherit ``ABC`` — mixing ABCMeta with
    GObject's metaclass causes a metaclass conflict in GTK subclasses.
    The ``@abstractmethod`` markers are enforced statically by type checkers.
    """

    _editor: "AbstractEditor"
    _state: SearchState  # dialog-local scratch copy
    _live_state: SearchState  # window's shared live state
    _tab_manager: "AbstractTabManager | None"
    _checks: "dict[str, HasGetActive]"

    @abstractmethod
    def get_find_text(self) -> str:
        """Return the current text in the find entry."""

    @abstractmethod
    def get_replace_text(self) -> str:
        """Return the current text in the replace entry."""

    def close_dialog(self) -> None:
        """Close the dialog. No-op in pure-logic / test context."""

    def commit_entries(self) -> None:
        """Sync entry text and checkbox state into scratch, then commit to live."""
        text = self.get_find_text()
        _sync_options_to_state(self._checks, self._state)
        self._state.push_find(text)
        self._state.replace_string = self.get_replace_text()
        self._state.push_replace(self._state.replace_string)
        self._state.commit_to(self._live_state)

    def handle_find(self) -> None:
        self.commit_entries()
        if self._live_state.search_backward:
            self._editor.find_previous(self._live_state)
        else:
            self._editor.find_next(self._live_state)

    def _find_current_match(self) -> bool:
        if self._live_state.search_backward:
            return self._editor.find_previous(self._live_state)
        return self._editor.find_next(self._live_state)

    def handle_replace(self) -> bool:
        self.commit_entries()
        if not self._find_current_match():
            return False
        return self._editor.replace_current(
            self._live_state.replace_string, self._live_state
        )

    def handle_replace_and_find(self) -> bool:
        self.commit_entries()
        if not self._find_current_match():
            return False
        buffer = self._editor.get_buffer()
        start_offset = 0
        if buffer.get_has_selection():
            sel_start, _sel_end = buffer.get_selection_bounds()
            start_offset = sel_start.get_offset()
        self._editor.replace_current(self._live_state.replace_string, self._live_state)
        if self._live_state.search_backward:
            buffer.place_cursor(buffer.get_iter_at_offset(start_offset))
            found = self._editor.find_previous(self._live_state)
        else:
            found = self._editor.find_next(self._live_state)
        if found and not self._live_state.keep_dialog:
            self.close_dialog()
        return found

    def handle_replace_all(self, scope: str) -> int:
        self.commit_entries()
        if scope == "all_tabs" and self._tab_manager is not None:
            total = 0
            for editor in self._get_all_editors():
                total += editor.replace_all(
                    self._live_state.replace_string, "window", self._live_state
                )
        else:
            total = self._editor.replace_all(
                self._live_state.replace_string, scope, self._live_state
            )
        return total

    def _get_all_editors(self) -> "list[AbstractEditor]":
        if self._tab_manager is None:
            return [self._editor]
        editors = [
            tab.get_editor()
            for i in range(self._tab_manager.get_tab_count())
            if (tab := self._tab_manager.get_nth_tab(i)) is not None
        ]
        return editors or [self._editor]

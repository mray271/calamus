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

    A single instance is owned by CalamusWindow and passed to every
    dialog and no-dialog action so that history and flags persist
    across invocations.
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

    def prepare_for_dialog_open(self) -> None:
        """Prepare state for a fresh dialog open.

        Resets only the dialog-local UI flags so the widgets initialize to
        sensible defaults: ``search_backward`` and ``keep_dialog`` are cleared
        (they are per-session UI choices, not part of the "last search").
        History cursors are reset so ↑/↓ recall starts from the most-recent
        entry.

        ``use_regex``, ``case_sensitive``, ``whole_word``, ``find_history``,
        and ``replace_string`` are intentionally **preserved** — the dialog
        pre-populates from them so the user sees the last-used settings, and
        Find Again / Replace Again continue to use those settings unchanged
        unless the user explicitly clicks an action button.
        """
        self.search_backward = False
        self.keep_dialog = False
        self.reset_history_cursor()


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

    Note: intentionally does *not* inherit ``ABC`` — mixing ABCMeta with
    GObject's metaclass causes a metaclass conflict in GTK subclasses.
    The ``@abstractmethod`` markers are enforced statically by type checkers.
    """

    _editor: "AbstractEditor"
    _state: SearchState
    _checks: "dict[str, HasGetActive]"

    @abstractmethod
    def get_find_text(self) -> str:
        """Return the current text in the find entry."""

    def close_dialog(self) -> None:
        """Close the dialog. No-op in pure-logic / test context."""

    def handle_find(self) -> bool:
        """Execute a find action. Returns True if a match was found."""
        text = self.get_find_text()
        _sync_options_to_state(self._checks, self._state)
        self._state.push_find(text)
        if self._state.search_backward:
            found = self._editor.find_previous(self._state)
        else:
            found = self._editor.find_next(self._state)
        if found and not self._state.keep_dialog:
            self.close_dialog()
        return found


class ReplaceDialogLogic:
    """Pure-Python handler logic for the Replace dialog.

    Subclassed by ``ReplaceDialog`` (GTK) and used directly in tests.
    Subclasses must implement :meth:`get_find_text` and
    :meth:`get_replace_text`; override :meth:`close_dialog` to dismiss a window.

    Note: intentionally does *not* inherit ``ABC`` — mixing ABCMeta with
    GObject's metaclass causes a metaclass conflict in GTK subclasses.
    The ``@abstractmethod`` markers are enforced statically by type checkers.
    """

    _editor: "AbstractEditor"
    _state: SearchState
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
        """Sync entry text and checkbox state into ``_state``."""
        text = self.get_find_text()
        _sync_options_to_state(self._checks, self._state)
        self._state.push_find(text)
        self._state.replace_string = self.get_replace_text()
        self._state.push_replace(self._state.replace_string)

    def handle_find(self) -> None:
        self.commit_entries()
        if self._state.search_backward:
            self._editor.find_previous(self._state)
        else:
            self._editor.find_next(self._state)

    def handle_replace(self) -> None:
        self.commit_entries()
        self._editor.replace_current(self._state.replace_string, self._state)

    def handle_replace_and_find(self) -> bool:
        self.commit_entries()
        found = self._editor.replace_and_find(self._state.replace_string, self._state)
        if found and not self._state.keep_dialog:
            self.close_dialog()
        return found

    def handle_replace_all(self, scope: str) -> int:
        self.commit_entries()
        if scope == "all_tabs" and self._tab_manager is not None:
            total = 0
            for editor in self._get_all_editors():
                total += editor.replace_all(
                    self._state.replace_string, "window", self._state
                )
        else:
            total = self._editor.replace_all(
                self._state.replace_string, scope, self._state
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

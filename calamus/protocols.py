"""Structural protocols for cross-cutting interfaces.

These protocols enable static type checking (mypy/pyright) across unrelated
class hierarchies that share a common behavioral interface but have no shared
ancestor.  They complement the ABC-based abstractions within each hierarchy.

Note: ``@runtime_checkable`` is deliberately omitted.  Runtime ``isinstance``
checks against a Protocol only verify attribute *existence*, not signatures —
which gives a false sense of safety.  Enforcement here is static-only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk


class HasWidget(Protocol):
    """Structural protocol for objects that wrap and expose a GTK widget.

    Satisfied by all UI component types in Calamus:
    ``AbstractEditor``, ``AbstractPreview``, ``AbstractDirectoryPane``,
    ``AbstractTab``, and ``AbstractTabManager``.
    """

    def get_widget(self) -> Gtk.Widget:
        """Return the underlying GTK widget for embedding in the UI."""
        ...


class Zoomable(Protocol):
    """Structural protocol for panes that support independent zoom.

    Satisfied by ``AbstractEditor``, ``AbstractPreview``, and
    ``AbstractDirectoryPane``.  Enables generic zoom dispatch in
    ``CalamusWindow`` without coupling to any concrete pane type.
    """

    def zoom_by(self, factor: float) -> None:
        """Scale the pane content by *factor* (>1 zooms in, <1 zooms out)."""
        ...

    def reset_zoom(self) -> None:
        """Restore the pane content to its default zoom level."""
        ...

"""Printing abstractions for Calamus."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

import gi

gi.require_version("Gtk", "4.0")

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")

from gi.repository import Gtk, PangoCairo

from calamus.mermaid_support import get_mermaid_init_script, get_mermaid_script_tag
from calamus.renderer import AbstractMarkdownRenderer, MistuneRenderer


class AbstractPrinter(ABC):
    """Defines printing behavior."""

    @abstractmethod
    def print_document(self, markdown_text: str, parent: Gtk.Window) -> None:
        """Show a print dialog for the document."""

    @abstractmethod
    def print_preview(self, markdown_text: str, parent: Gtk.Window) -> None:
        """Show a print preview for the document."""


class GtkPrinter(AbstractPrinter):
    """Gtk-based printer implementation."""

    def __init__(self, renderer: AbstractMarkdownRenderer | None = None) -> None:
        self._renderer = renderer or MistuneRenderer()
        self._last_rendered_html = ""

    def print_document(self, markdown_text: str, parent: Gtk.Window) -> None:
        self._run(markdown_text, parent, Gtk.PrintOperationAction.PRINT_DIALOG)

    def print_preview(self, markdown_text: str, parent: Gtk.Window) -> None:
        self._run(markdown_text, parent, Gtk.PrintOperationAction.PREVIEW)

    def _run(
        self,
        markdown_text: str,
        parent: Gtk.Window,
        action: Gtk.PrintOperationAction,
    ) -> None:
        operation = Gtk.PrintOperation.new()
        operation.connect("begin-print", self._on_begin_print)
        operation.connect("draw-page", self._on_draw_page, markdown_text)
        self._last_rendered_html = self._build_html(markdown_text)
        operation.run(action, parent)

    def _build_html(self, markdown_text: str) -> str:
        body = self._renderer.render(markdown_text)
        return """<html><head>{script}{init}</head><body>{body}</body></html>""".format(
            script=get_mermaid_script_tag(),
            init=get_mermaid_init_script(),
            body=body,
        )

    def _on_begin_print(
        self, operation: Gtk.PrintOperation, context: Gtk.PrintContext
    ) -> None:
        operation.set_n_pages(1)

    def _on_draw_page(
        self,
        operation: Gtk.PrintOperation,
        context: Gtk.PrintContext,
        page_num: int,
        markdown_text: str,
    ) -> None:
        plain_text = re.sub(r"<[^>]+>", "", self._renderer.render(markdown_text))
        layout = context.create_pango_layout()
        layout.set_text(plain_text)
        layout.set_width(int((context.get_width() - 144) * PangoCairo.Pango.SCALE))
        cairo_context = context.get_cairo_context()
        cairo_context.move_to(72, 72)
        PangoCairo.show_layout(cairo_context, layout)

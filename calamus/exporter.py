"""Export Markdown to HTML, PDF, and ODT."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")

gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from calamus.mermaid_support import (
    get_mermaid_init_script,
    get_mermaid_script_tag,
    preprocess_markdown_for_static_export,
)
from calamus.renderer import AbstractMarkdownRenderer, MistuneRenderer


class AbstractExporter(ABC):
    """Defines export behavior."""

    def __init__(self, renderer: AbstractMarkdownRenderer | None = None) -> None:
        self._renderer = renderer or MistuneRenderer()

    @abstractmethod
    def export(self, markdown_text: str, dest_path: str) -> None:
        """Export Markdown text to the destination path."""

    @abstractmethod
    def get_file_filter(self) -> Gtk.FileFilter:
        """Return the file filter for the save dialog."""

    @abstractmethod
    def get_file_suffix(self) -> str:
        """Return the output file suffix."""

    @abstractmethod
    def get_dialog_title(self) -> str:
        """Return the export dialog title."""

    def run_export_dialog(self, parent: Gtk.Window, markdown_text: str) -> None:
        """Run the export dialog and write the selected file."""
        dialog = Gtk.FileDialog.new()
        dialog.set_title(self.get_dialog_title())
        filters = GioListStoreFactory.create(self.get_file_filter())
        dialog.set_filters(filters)
        dialog.save(
            parent,
            None,
            lambda dlg, result: self._on_save_finish(
                dlg, result, markdown_text, parent
            ),
        )

    def _on_save_finish(
        self,
        dialog: Gtk.FileDialog,
        result: GioAsyncResult,
        markdown_text: str,
        parent: Gtk.Window,
    ) -> None:
        try:
            gfile = dialog.save_finish(result)
            if gfile is None:
                return
            path = gfile.get_path() or ""
            if not path.endswith(self.get_file_suffix()):
                path += self.get_file_suffix()
            self.export(markdown_text, path)
        except GLib.Error as error:
            self._show_error(parent, str(error))
        except OSError as error:
            self._show_error(parent, str(error))

    def _show_error(self, parent: Gtk.Window, message: str) -> None:
        dialog = Adw.MessageDialog.new(parent, "Export Error", message)
        dialog.add_response("ok", "OK")
        dialog.present()


class HtmlExporter(AbstractExporter):
    """Export Markdown as Mermaid-enabled HTML."""

    def export(self, markdown_text: str, dest_path: str) -> None:
        if not dest_path.endswith(self.get_file_suffix()):
            dest_path += self.get_file_suffix()
        html_body = self._renderer.render(markdown_text)
        html_text = """<!DOCTYPE html>
<html>
<head>
<meta charset=\"utf-8\">
{mermaid_script}
{mermaid_init_script}
</head>
<body>
{body}
</body>
</html>
""".format(
            mermaid_script=get_mermaid_script_tag(),
            mermaid_init_script=get_mermaid_init_script(),
            body=html_body,
        )
        Path(dest_path).write_text(html_text, encoding="utf-8")

    def get_file_filter(self) -> Gtk.FileFilter:
        file_filter = Gtk.FileFilter()
        file_filter.set_name("HTML files")
        file_filter.add_pattern("*.html")
        return file_filter

    def get_file_suffix(self) -> str:
        return ".html"

    def get_dialog_title(self) -> str:
        return "Export as HTML"


class PdfExporter(AbstractExporter):
    """Export Markdown as PDF."""

    def export(self, markdown_text: str, dest_path: str) -> None:
        from weasyprint import HTML

        processed = preprocess_markdown_for_static_export(markdown_text)
        html_body = self._renderer.render(processed)
        HTML(string=f"<html><body>{html_body}</body></html>").write_pdf(dest_path)

    def get_file_filter(self) -> Gtk.FileFilter:
        file_filter = Gtk.FileFilter()
        file_filter.set_name("PDF files")
        file_filter.add_pattern("*.pdf")
        return file_filter

    def get_file_suffix(self) -> str:
        return ".pdf"

    def get_dialog_title(self) -> str:
        return "Export as PDF"


class OdtExporter(AbstractExporter):
    """Export Markdown as ODT."""

    def export(self, markdown_text: str, dest_path: str) -> None:
        from odf.opendocument import OpenDocumentText
        from odf.text import P

        processed = preprocess_markdown_for_static_export(markdown_text)
        html_body = self._renderer.render(processed)
        document = OpenDocumentText()
        for line in html_body.splitlines():
            document.text.addElement(P(text=line))
        document.save(dest_path)

    def get_file_filter(self) -> Gtk.FileFilter:
        file_filter = Gtk.FileFilter()
        file_filter.set_name("ODT files")
        file_filter.add_pattern("*.odt")
        return file_filter

    def get_file_suffix(self) -> str:
        return ".odt"

    def get_dialog_title(self) -> str:
        return "Export as ODT"


class GioAsyncResult:
    """Minimal typing shim for async dialog results."""


class GioListStoreFactory:
    """Creates filter list models without importing Gio at module import time."""

    @staticmethod
    def create(file_filter: Gtk.FileFilter):
        from gi.repository import Gio

        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(file_filter)
        return filters

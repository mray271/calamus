"""Unit tests for calamus.exporter classes."""

import pytest

# ---------------------------------------------------------------------------
# HtmlExporter
# ---------------------------------------------------------------------------


def test_html_exporter_suffix():
    from calamus.exporter import HtmlExporter

    assert HtmlExporter().get_file_suffix() == ".html"


def test_html_exporter_dialog_title():
    from calamus.exporter import HtmlExporter

    assert "HTML" in HtmlExporter().get_dialog_title()


def test_html_exporter_writes_file(tmp_path):
    from calamus.exporter import HtmlExporter

    exporter = HtmlExporter()
    dest = str(tmp_path / "output.html")
    exporter.export("# Hello\n\nThis is a **test**.", dest)
    content = (tmp_path / "output.html").read_text()
    assert "<h1" in content
    assert "<strong>" in content


def test_html_exporter_includes_mermaid_script(tmp_path):
    from calamus.exporter import HtmlExporter

    exporter = HtmlExporter()
    dest = str(tmp_path / "output.html")
    exporter.export("# Hello", dest)
    content = (tmp_path / "output.html").read_text()
    assert "mermaid" in content


def test_html_exporter_with_mermaid_block(tmp_path):
    from calamus.exporter import HtmlExporter

    exporter = HtmlExporter()
    dest = str(tmp_path / "diagram.html")
    md = "# Diagram\n\n```mermaid\ngraph TD\nA-->B\n```\n"
    exporter.export(md, dest)
    content = (tmp_path / "diagram.html").read_text()
    assert "mermaid" in content


def test_html_exporter_appends_suffix_if_missing(tmp_path):
    from calamus.exporter import HtmlExporter

    exporter = HtmlExporter()
    dest = str(tmp_path / "output")  # no .html
    exporter.export("# Hello", dest)
    assert (tmp_path / "output.html").exists()


# ---------------------------------------------------------------------------
# PdfExporter
# ---------------------------------------------------------------------------


def test_pdf_exporter_suffix():
    from calamus.exporter import PdfExporter

    assert PdfExporter().get_file_suffix() == ".pdf"


def test_pdf_exporter_dialog_title():
    from calamus.exporter import PdfExporter

    assert "PDF" in PdfExporter().get_dialog_title()


def test_pdf_exporter_preprocesses_mermaid(monkeypatch):
    """PdfExporter should call preprocess_markdown_for_static_export before rendering."""
    from calamus import exporter as exporter_module

    calls = []

    def fake_preprocess(text):
        calls.append(text)
        return text

    monkeypatch.setattr(
        exporter_module, "preprocess_markdown_for_static_export", fake_preprocess
    )

    # Mock WeasyPrint's HTML class to avoid actual PDF rendering which
    # segfaults in headless/minimal containers (Pango font lookup crash).
    import unittest.mock as mock
    fake_html = mock.MagicMock()
    fake_html.return_value.write_pdf = mock.MagicMock()
    monkeypatch.setattr("calamus.exporter.HTML", fake_html, raising=False)

    from calamus.exporter import PdfExporter

    exporter = PdfExporter()
    md = "# Hello\n```mermaid\ngraph TD\nA-->B\n```"
    exporter.export(md, "/tmp/test_calamus_output.pdf")

    assert len(calls) == 1
    assert "graph TD" in calls[0]


# ---------------------------------------------------------------------------
# OdtExporter
# ---------------------------------------------------------------------------


def test_odt_exporter_suffix():
    from calamus.exporter import OdtExporter

    assert OdtExporter().get_file_suffix() == ".odt"


def test_odt_exporter_dialog_title():
    from calamus.exporter import OdtExporter

    assert "ODT" in OdtExporter().get_dialog_title()


def test_odt_exporter_preprocesses_mermaid(monkeypatch):
    """OdtExporter should call preprocess_markdown_for_static_export before rendering."""
    from calamus import exporter as exporter_module

    calls = []

    def fake_preprocess(text):
        calls.append(text)
        return text

    monkeypatch.setattr(
        exporter_module, "preprocess_markdown_for_static_export", fake_preprocess
    )

    from calamus.exporter import OdtExporter

    exporter = OdtExporter()
    md = "# Hello\n```mermaid\ngraph TD\nA-->B\n```"
    try:
        exporter.export(md, "/tmp/test_calamus_output.odt")
    except Exception:
        pass  # odfpy may not be installed

    assert len(calls) == 1
    assert "graph TD" in calls[0]


# ---------------------------------------------------------------------------
# AbstractExporter interface
# ---------------------------------------------------------------------------


def test_all_exporters_are_abstract_exporter_subclasses():
    from calamus.exporter import (
        AbstractExporter,
        HtmlExporter,
        OdtExporter,
        PdfExporter,
    )

    for cls in (HtmlExporter, PdfExporter, OdtExporter):
        assert issubclass(cls, AbstractExporter)


def test_all_exporters_have_file_filter():
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    from calamus.exporter import HtmlExporter, OdtExporter, PdfExporter

    for cls in (HtmlExporter, PdfExporter, OdtExporter):
        f = cls().get_file_filter()
        assert isinstance(f, Gtk.FileFilter)

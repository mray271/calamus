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


def test_html_exporter_silences_oserror(tmp_path, monkeypatch):
    from pathlib import Path

    from calamus.exporter import HtmlExporter

    def fail_write(self, *args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", fail_write)
    HtmlExporter().export("# Hello", str(tmp_path / "out.html"))  # must not raise


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


def test_html_exporter_appends_suffix_if_missing_and_keeps_existing_suffix(tmp_path):
    from calamus.exporter import HtmlExporter

    exporter = HtmlExporter()
    dest = str(tmp_path / "output.html")
    exporter.export("# Hello", dest)
    assert (tmp_path / "output.html").exists()


# ---------------------------------------------------------------------------
# AbstractExporter dialog wiring / save handling
# ---------------------------------------------------------------------------


class _DummyExporter:
    def __init__(self):
        self.export_calls = []
        self.filter = object()
        self.title = "Dummy export"
        self.suffix = ".dummy"

    def export(self, markdown_text: str, dest_path: str) -> None:
        self.export_calls.append((markdown_text, dest_path))

    def get_file_filter(self):
        return self.filter

    def get_file_suffix(self) -> str:
        return self.suffix

    def get_dialog_title(self) -> str:
        return self.title


def test_run_export_dialog_wires_title_filters_and_save_callback(monkeypatch):
    from calamus import exporter as exporter_module

    dummy = _DummyExporter()
    calls = {}

    class FakeDialog:
        def set_title(self, title):
            calls["title"] = title

        def set_filters(self, filters):
            calls["filters"] = filters

        def save(self, parent, cancellable, callback):
            calls["save_args"] = (parent, cancellable)
            calls["callback"] = callback

    monkeypatch.setattr(exporter_module.Gtk.FileDialog, "new", lambda: FakeDialog())
    monkeypatch.setattr(
        exporter_module.GioListStoreFactory,
        "create",
        lambda file_filter: ("filters", file_filter),
    )

    exporter_module.AbstractExporter.run_export_dialog(
        dummy, parent="parent-window", markdown_text="# hello"
    )

    assert calls["title"] == "Dummy export"
    assert calls["filters"] == ("filters", dummy.filter)
    assert calls["save_args"] == ("parent-window", None)
    assert callable(calls["callback"])


def test_on_save_finish_appends_suffix_and_exports(monkeypatch):
    from calamus import exporter as exporter_module

    dummy = _DummyExporter()

    class FakeFile:
        def get_path(self):
            return "/tmp/output"

    class FakeDialog:
        def save_finish(self, result):
            return FakeFile()

    exporter_module.AbstractExporter._on_save_finish(
        dummy,
        FakeDialog(),
        result=object(),
        markdown_text="# hello",
        parent="parent-window",
    )

    assert dummy.export_calls == [("# hello", "/tmp/output.dummy")]


def test_on_save_finish_ignores_cancelled_dialog(monkeypatch):
    from calamus import exporter as exporter_module

    dummy = _DummyExporter()

    class FakeDialog:
        def save_finish(self, result):
            return None

    exporter_module.AbstractExporter._on_save_finish(
        dummy,
        FakeDialog(),
        result=object(),
        markdown_text="# hello",
        parent="parent-window",
    )

    assert dummy.export_calls == []


def test_on_save_finish_routes_glib_error_to_show_error(monkeypatch):
    from calamus import exporter as exporter_module

    dummy = _DummyExporter()
    shown = {}

    class FakeGLibError(Exception):
        pass

    class FakeDialog:
        def save_finish(self, result):
            raise FakeGLibError("broken")

    monkeypatch.setattr(exporter_module.GLib, "Error", FakeGLibError)
    dummy._show_error = lambda parent, message: shown.update(
        parent=parent, message=message
    )

    exporter_module.AbstractExporter._on_save_finish(
        dummy,
        FakeDialog(),
        result=object(),
        markdown_text="# hello",
        parent="parent-window",
    )

    assert shown == {"parent": "parent-window", "message": "broken"}


def test_on_save_finish_routes_oserror_to_show_error(monkeypatch):
    from calamus import exporter as exporter_module

    dummy = _DummyExporter()
    shown = {}

    class FakeDialog:
        def save_finish(self, result):
            raise OSError("disk full")

    dummy._show_error = lambda parent, message: shown.update(
        parent=parent, message=message
    )

    exporter_module.AbstractExporter._on_save_finish(
        dummy,
        FakeDialog(),
        result=object(),
        markdown_text="# hello",
        parent="parent-window",
    )

    assert shown == {"parent": "parent-window", "message": "disk full"}


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
    # PdfExporter does `from weasyprint import HTML` lazily inside export(),
    # so we must patch at the weasyprint module level, not calamus.exporter.
    import unittest.mock as mock

    fake_html = mock.MagicMock()
    fake_html.return_value.write_pdf = mock.MagicMock()
    monkeypatch.setattr("weasyprint.HTML", fake_html)

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

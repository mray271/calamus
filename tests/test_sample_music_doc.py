"""Integration tests using samples/why_claude_sonnet_fails_to_discover_music.md.

This sample is a rich real-world document that exercises several patterns not
fully covered by the unit fixtures:

  - Five Mermaid diagrams in a single document (graph TD, mindmap, graph LR)
  - An %%{init: ...}%% inline directive on a Mermaid block (mindmap)
  - Standard Markdown image syntax with a relative subfolder path
  - Raw HTML <img> tags (with height=) inside GFM table cells
  - External hyperlinks, including links that wrap <img> tags
  - Multi-column GFM tables with mixed cell content
  - Blockquotes, bold/italic, horizontal rules, and fenced code blocks

These tests verify that the renderer and exporter handle the full combination
without dropping content, mangling relative paths, or crashing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SAMPLE_PATH = (
    Path(__file__).parent.parent
    / "samples"
    / "why_claude_sonnet_fails_to_discover_music.md"
)
SAMPLE_MD = SAMPLE_PATH.read_text(encoding="utf-8")

IMAGE_SUBDIR = "why_claude_sonnet_fails_to_discover_music"


# ---------------------------------------------------------------------------
# Fixture sanity
# ---------------------------------------------------------------------------


def test_sample_file_exists():
    assert SAMPLE_PATH.exists(), f"Sample file not found: {SAMPLE_PATH}"


def test_sample_contains_five_mermaid_blocks():
    assert SAMPLE_MD.count("```mermaid") == 5


def test_sample_contains_init_directive():
    assert "%%{init:" in SAMPLE_MD


def test_sample_contains_relative_subfolder_image():
    assert f"./{IMAGE_SUBDIR}/" in SAMPLE_MD


def test_sample_contains_html_img_tags_with_height():
    assert re.search(r'<img\s[^>]*height="\d+"', SAMPLE_MD) is not None


def test_sample_contains_external_links():
    # Check for the complete Markdown link syntax to avoid an incomplete-URL-substring match
    assert "](https://adst.bandcamp.com)" in SAMPLE_MD
    assert "](https://www.wammies.org)" in SAMPLE_MD


# ---------------------------------------------------------------------------
# Renderer — structural output
# ---------------------------------------------------------------------------


def test_renderer_produces_html_not_raw_markdown():
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(SAMPLE_MD)
    assert "<h1" in html
    assert "# Why Claude Sonnet" not in html, "raw Markdown heading leaked through"


def test_renderer_no_raw_mermaid_fences_in_output():
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(SAMPLE_MD)
    assert "```mermaid" not in html, "raw mermaid fence leaked into HTML output"


def test_renderer_all_five_mermaid_diagrams_rendered():
    """Each of the 5 Mermaid blocks must produce either a <pre class="mermaid">
    (browser-side) or a data-URI <img> (mmdc pre-render)."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(SAMPLE_MD)
    pre_count = html.count('<pre class="mermaid">')
    img_count = html.count("data:image/svg+xml;base64,")
    assert (
        pre_count + img_count == 5
    ), f"Expected 5 rendered Mermaid blocks, got {pre_count} <pre> + {img_count} <img>"


def test_renderer_init_directive_mindmap_rendered():
    """The mindmap block with the %%{init: ...}%% directive must be rendered,
    not silently dropped."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(SAMPLE_MD)
    # The mindmap label "Search Failure" must survive in one of the two forms.
    pre_has_mindmap = "mindmap" in html and "Search Failure" in html
    img_has_data_uri = "data:image/svg+xml;base64," in html
    assert (
        pre_has_mindmap or img_has_data_uri
    ), "Mindmap diagram with %%{init:%% directive appears to have been dropped"


def test_renderer_relative_subfolder_image_path_preserved():
    """The ./subdir/image.png reference must survive through the renderer
    so WebKit can resolve the image relative to the document's base URI."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(SAMPLE_MD)
    assert (
        f"{IMAGE_SUBDIR}/ADST_logo.png" in html
    ), "Relative subfolder image path was not preserved in rendered HTML"


def test_renderer_html_img_tags_preserved_in_table_cells():
    """Raw <img> tags embedded in GFM table cells must pass through
    the renderer (HTMLRenderer escape=False) without being entity-escaped."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(SAMPLE_MD)
    assert "<img" in html, "No <img> tags found — raw HTML may have been escaped"
    assert "&lt;img" not in html, "<img> was HTML-escaped in output"


def test_renderer_external_hyperlinks_present():
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(SAMPLE_MD)
    assert 'href="https://adst.bandcamp.com"' in html
    assert 'href="https://www.wammies.org"' in html


def test_renderer_gfm_tables_rendered():
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(SAMPLE_MD)
    assert "<table" in html
    assert "<th" in html or "<td" in html


def test_renderer_blockquote_rendered():
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(SAMPLE_MD)
    assert "<blockquote>" in html


def test_renderer_bold_and_italic_rendered():
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(SAMPLE_MD)
    assert "<strong>" in html
    assert "<em>" in html


def test_renderer_horizontal_rule_rendered():
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(SAMPLE_MD)
    assert "<hr" in html


# ---------------------------------------------------------------------------
# Renderer — Mermaid SVG output
# ---------------------------------------------------------------------------


def test_renderer_all_five_mermaid_diagrams_rendered():
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(SAMPLE_MD)
    assert html.count("data:image/svg+xml;base64,") == 5
    assert '<pre class="mermaid">' not in html


# ---------------------------------------------------------------------------
# Exporter — full HTML export
# ---------------------------------------------------------------------------


def test_html_exporter_renders_sample_without_error(tmp_path):
    from calamus.exporter import HtmlExporter

    dest = str(tmp_path / "music_doc.html")
    HtmlExporter().export(SAMPLE_MD, dest)
    content = (tmp_path / "music_doc.html").read_text(encoding="utf-8")
    assert "<h1" in content
    assert "ADST" in content


def test_html_exporter_sample_contains_mermaid_support(tmp_path):
    from calamus.exporter import HtmlExporter

    dest = str(tmp_path / "music_doc.html")
    HtmlExporter().export(SAMPLE_MD, dest)
    content = (tmp_path / "music_doc.html").read_text(encoding="utf-8")
    assert "mermaid" in content


def test_html_exporter_sample_preserves_external_links(tmp_path):
    from calamus.exporter import HtmlExporter

    dest = str(tmp_path / "music_doc.html")
    HtmlExporter().export(SAMPLE_MD, dest)
    content = (tmp_path / "music_doc.html").read_text(encoding="utf-8")
    assert 'href="https://adst.bandcamp.com"' in content


def test_html_exporter_sample_no_raw_mermaid_fences(tmp_path):
    from calamus.exporter import HtmlExporter

    dest = str(tmp_path / "music_doc.html")
    HtmlExporter().export(SAMPLE_MD, dest)
    content = (tmp_path / "music_doc.html").read_text(encoding="utf-8")
    assert "```mermaid" not in content


def test_html_exporter_sample_img_tags_not_escaped(tmp_path):
    from calamus.exporter import HtmlExporter

    dest = str(tmp_path / "music_doc.html")
    HtmlExporter().export(SAMPLE_MD, dest)
    content = (tmp_path / "music_doc.html").read_text(encoding="utf-8")
    assert "&lt;img" not in content, "<img> tags were HTML-escaped in export output"

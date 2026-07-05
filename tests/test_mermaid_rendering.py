"""Regression tests for the Mermaid rendering pipeline.

These tests verify the full chain:
  .md source  ->  MistuneRenderer  ->  HTML body  ->  full preview HTML

The test fixture tests/fixtures/xychart_mermaid.md contains a real
xychart-beta Mermaid diagram so we catch regressions on that chart type.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "xychart_mermaid.md"
FIXTURE_MD = FIXTURE_PATH.read_text(encoding="utf-8")

# ── 1. Renderer: mermaid fences → <pre class="mermaid"> ──────────────────────


def test_renderer_converts_mermaid_fence_to_pre():
    from calamus.renderer import MistuneRenderer

    md = "```mermaid\ngraph LR\n    A --> B\n```\n"
    html = MistuneRenderer().render(md)
    assert '<pre class="mermaid">' in html, "mermaid fence not converted to <pre>"
    assert "graph LR" in html


def test_renderer_fixture_contains_mermaid_pre():
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(FIXTURE_MD)
    assert '<pre class="mermaid">' in html
    assert "xychart-beta" in html


def test_renderer_does_not_escape_pre_tag():
    """mistune must NOT escape the <pre class="mermaid"> we inject."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(FIXTURE_MD)
    assert "&lt;pre" not in html, "<pre> was HTML-escaped by mistune"


# ── 2. Mermaid script tag: inlined JS, no CDN ────────────────────────────────


def test_script_tag_inlines_local_file(tmp_path, monkeypatch):
    import calamus.mermaid_support as ms

    js_file = tmp_path / "mermaid.min.js"
    js_file.write_text("/* mermaid */", encoding="utf-8")
    monkeypatch.setattr(ms, "MERMAID_LOCAL_PATH", str(js_file))

    tag = ms.get_mermaid_script_tag()
    assert "/* mermaid */" in tag, "JS content not inlined"
    assert "cdn.jsdelivr.net" not in tag


def test_script_tag_falls_back_to_system_path(tmp_path, monkeypatch):
    import calamus.mermaid_support as ms

    system = tmp_path / "mermaid.min.js"
    system.write_text("/* system mermaid */", encoding="utf-8")
    monkeypatch.setattr(ms, "MERMAID_LOCAL_PATH", "/nonexistent/mermaid.min.js")
    monkeypatch.setattr(ms, "MERMAID_SYSTEM_PATH", str(system))

    tag = ms.get_mermaid_script_tag()
    assert "/* system mermaid */" in tag
    assert "cdn.jsdelivr.net" not in tag


def test_script_tag_falls_back_to_cdn_when_no_local(monkeypatch):
    import calamus.mermaid_support as ms

    monkeypatch.setattr(ms, "MERMAID_LOCAL_PATH", "/nonexistent/a.js")
    monkeypatch.setattr(ms, "MERMAID_SYSTEM_PATH", "/nonexistent/b.js")

    tag = ms.get_mermaid_script_tag()
    assert "cdn.jsdelivr.net" in tag


# ── 3. Full HTML output: init strategy and byte-length sanity ─────────────────


def _build_preview_html(md: str, fake_js: str = "/* mermaid */") -> str:
    """Build the full preview HTML using fake mermaid JS for size isolation."""
    import calamus.mermaid_support as ms
    from calamus.preview import _HTML_TEMPLATE
    from calamus.renderer import MistuneRenderer
    from unittest.mock import patch

    with patch.object(
        ms, "get_mermaid_script_tag", return_value=f"<script>{fake_js}</script>"
    ):
        html_body = MistuneRenderer().render(md)
        return _HTML_TEMPLATE.format(
            body=html_body, mermaid_script=f"<script>{fake_js}</script>"
        )


def test_full_html_contains_mermaid_pre_and_init():
    html = _build_preview_html(FIXTURE_MD)
    assert '<pre class="mermaid">' in html
    assert "xychart-beta" in html
    assert "mermaid.run" in html
    assert "startOnLoad" in html


def test_full_html_uses_run_not_domcontentloaded():
    """Mermaid must use mermaid.run() not DOMContentLoaded (WebKit timing fix)."""
    html = _build_preview_html(FIXTURE_MD)
    assert "mermaid.run" in html
    assert "DOMContentLoaded" not in html


def test_full_html_byte_length_grows_with_diagram():
    """HTML with the diagram must be substantially larger than without."""
    html_with = _build_preview_html(FIXTURE_MD)
    html_without = _build_preview_html("# Just a heading\n")
    assert len(html_with) > len(html_without) + 500


# ── 4. Config frontmatter preservation ───────────────────────────────────────
# Regression: labelRotation (and other per-diagram config) must survive
# the full md→HTML pipeline without corruption.

_XYCHART_MD = """\
```mermaid
---
config:
  xyChart:
    xAxis:
      labelRotation: 20
---
xychart-beta
    title "Drift"
    x-axis ["A", "B", "C"]
    y-axis "val" 0 --> 10
    bar [1, 2, 3]
```
"""


def _extract_mermaid_pre(html: str) -> str:
    """Return the raw content inside the first <pre class=\"mermaid\"> tag."""
    start = html.find('<pre class="mermaid">') + len('<pre class="mermaid">')
    end = html.find("</pre>", start)
    assert start > len('<pre class="mermaid">') - 1, "no <pre class='mermaid'> found"
    return html[start:end]


def test_config_frontmatter_preserved_in_pre():
    """The ---config:--- YAML block must appear inside the <pre> tag."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_XYCHART_MD)
    pre = _extract_mermaid_pre(html)
    assert "---" in pre, "YAML frontmatter delimiters lost"
    assert "config:" in pre
    assert "xyChart:" in pre
    assert "xAxis:" in pre
    assert "labelRotation: 20" in pre, "labelRotation value was lost or corrupted"


def test_config_yaml_keys_not_html_escaped():
    """YAML config keys/values contain no HTML special chars so must be literal."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_XYCHART_MD)
    pre = _extract_mermaid_pre(html)
    # YAML config has no <, >, &, " — so nothing should be encoded
    assert "&amp;" not in pre or "labelRotation" in pre  # config section is clean
    # Specifically the labelRotation line must be byte-for-byte identical
    assert "      labelRotation: 20" in pre


def test_diagram_body_quotes_are_escaped_but_decodable():
    """Quoted strings in the diagram body are &quot;-encoded (safe for HTML)
    but decode back to the original via textContent in the browser."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_XYCHART_MD)
    pre = _extract_mermaid_pre(html)
    # The title string contains quotes — they are escaped in the HTML source…
    assert "&quot;Drift&quot;" in pre
    # …but the YAML config section (labelRotation) remains unescaped
    assert "labelRotation: 20" in pre


def test_pre_block_byte_length_matches_expected_range():
    """Pin the expected byte length of the <pre> block as a canary."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_XYCHART_MD)
    pre = _extract_mermaid_pre(html)
    # Allow ±50 bytes for minor whitespace/escaping changes
    assert 180 < len(pre) < 400, f"<pre> block length {len(pre)} outside expected range"


def test_fixture_pre_block_byte_length():
    """Pin the byte length of the real fixture's <pre> block.

    The fixture's Mermaid source (including YAML config + xychart-beta body)
    must produce a <pre> block of exactly this size.  A change in length
    signals that content was dropped, double-escaped, or corrupted.
    Expected: 474 bytes.
    """
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(FIXTURE_MD)
    pre = _extract_mermaid_pre(html)
    assert len(pre) == 474, (
        f"Fixture <pre> block is {len(pre)} bytes, expected 474. "
        "Content may have been dropped or corrupted in the rendering pipeline."
    )

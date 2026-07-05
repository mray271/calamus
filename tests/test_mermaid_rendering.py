"""Regression tests for the Mermaid rendering pipeline.

Two rendering paths are tested:

  browser-side (mmdc absent):
    .md → MistuneRenderer → <pre class="mermaid"> blocks → mermaid.js in WebKit

  mmdc pre-render (mmdc present):
    .md → MistuneRenderer → preprocess_markdown_for_static_export
       → <img src="data:image/svg+xml;base64,…"> tags

Tests that depend on which path is active are guarded with MMDC_AVAILABLE.
Tests that must pass regardless of mmdc are written to accept either output.

Two distinct Mermaid configuration syntaxes are tested:

  YAML frontmatter (xychart_mermaid.md fixture):
    Placed between --- delimiters inside the mermaid fence.
    Example: ---\\nconfig:\\n  xyChart:\\n    xAxis:\\n      labelRotation: 20\\n---

  Inline directive (mermaid_directive.md fixture):
    Placed as the very first line of the mermaid fence using %%{...}%% syntax.
    Example: %%{init: {'theme': 'forest'}}%%
    Source: https://stackoverflow.com/a/66751560 (GLFM directive example)
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "xychart_mermaid.md"
FIXTURE_MD = FIXTURE_PATH.read_text(encoding="utf-8")

DIRECTIVE_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mermaid_directive.md"
DIRECTIVE_FIXTURE_MD = DIRECTIVE_FIXTURE_PATH.read_text(encoding="utf-8")

MMDC_AVAILABLE = shutil.which("mmdc") is not None

# ── 1. Renderer output shape ──────────────────────────────────────────────────


def test_renderer_produces_html_not_raw_markdown():
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(FIXTURE_MD)
    assert "<h1>" in html, "headings not rendered"
    assert "# Relativistic" not in html, "raw markdown leaked through"


def test_renderer_mermaid_fence_not_literal_backticks():
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(FIXTURE_MD)
    assert "```mermaid" not in html, "raw mermaid fence in output"


def test_renderer_fixture_contains_diagram():
    """Regardless of path, the diagram content must appear in the output."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(FIXTURE_MD)
    if MMDC_AVAILABLE:
        assert "data:image/svg+xml;base64," in html, "no SVG data URI from mmdc"
    else:
        assert '<pre class="mermaid">' in html, "no mermaid pre block"
        assert "xychart-beta" in html


def test_renderer_does_not_escape_injected_html():
    """mistune HTMLRenderer(escape=False) must pass injected HTML through."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(FIXTURE_MD)
    assert "&lt;pre" not in html, "<pre> was HTML-escaped by mistune"


# ── 2. Browser-side path (mmdc absent) ───────────────────────────────────────


@pytest.mark.skipif(MMDC_AVAILABLE, reason="mmdc present — browser-side path not used")
def test_browser_path_creates_pre_block():
    from calamus.renderer import MistuneRenderer

    md = "```mermaid\ngraph LR\n    A --> B\n```\n"
    html = MistuneRenderer().render(md)
    assert '<pre class="mermaid">' in html
    assert "graph LR" in html


@pytest.mark.skipif(MMDC_AVAILABLE, reason="mmdc present — browser-side path not used")
def test_browser_path_fixture_pre_block_byte_length():
    """Exact 474-byte pin on the <pre> block content — canary for corruption."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(FIXTURE_MD)
    start = html.find('<pre class="mermaid">') + len('<pre class="mermaid">')
    end = html.find("</pre>", start)
    pre = html[start:end]
    assert len(pre) == 474, (
        f"Fixture <pre> block is {len(pre)} bytes, expected 474. "
        "Content may have been dropped or corrupted."
    )


# ── 3. mmdc pre-render path ───────────────────────────────────────────────────


@pytest.mark.skipif(not MMDC_AVAILABLE, reason="mmdc not installed")
def test_mmdc_path_produces_svg_data_uri():
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(FIXTURE_MD)
    assert "data:image/svg+xml;base64," in html
    assert '<pre class="mermaid">' not in html


@pytest.mark.skipif(not MMDC_AVAILABLE, reason="mmdc not installed")
def test_mmdc_path_svg_contains_rotate_transform():
    """The pre-rendered SVG must include rotate(20) for labelRotation:20."""
    import base64
    import re
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(FIXTURE_MD)
    match = re.search(r"data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)", html)
    assert match, "no SVG data URI found"
    svg = base64.b64decode(match.group(1)).decode("utf-8", errors="replace")
    assert (
        "rotate(20)" in svg
    ), "labelRotation:20 from ---config:--- frontmatter not applied in SVG"


@pytest.mark.skipif(not MMDC_AVAILABLE, reason="mmdc not installed")
def test_mmdc_path_svg_larger_than_fallback():
    """A real rendered SVG must be substantially larger than the FallbackMermaidRenderer output."""
    import base64
    import re
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(FIXTURE_MD)
    match = re.search(r"data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)", html)
    assert match
    svg = base64.b64decode(match.group(1)).decode("utf-8", errors="replace")
    assert len(svg) > 5000, f"SVG only {len(svg)} bytes — may be a placeholder"


# ── 4. Mermaid script tag: inlined JS, no CDN ────────────────────────────────


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


# ── 5. Full HTML output ───────────────────────────────────────────────────────


def _build_preview_html(md: str, fake_js: str = "/* mermaid */") -> str:
    import calamus.mermaid_support as ms
    from calamus.preview import _HTML_TEMPLATE
    from calamus.renderer import MistuneRenderer

    with patch.object(
        ms, "get_mermaid_script_tag", return_value=f"<script>{fake_js}</script>"
    ):
        html_body = MistuneRenderer().render(md)
        return _HTML_TEMPLATE.format(
            body=html_body, mermaid_script=f"<script>{fake_js}</script>"
        )


def test_full_html_uses_run_not_domcontentloaded():
    """mermaid.run() must be used (not DOMContentLoaded) for WebKit timing."""
    html = _build_preview_html(FIXTURE_MD)
    assert "mermaid.run" in html
    assert "DOMContentLoaded" not in html


def test_full_html_byte_length_grows_with_diagram():
    html_with = _build_preview_html(FIXTURE_MD)
    html_without = _build_preview_html("# Just a heading\n")
    assert len(html_with) > len(html_without) + 500


# ── 6. Config frontmatter preservation (browser-side path only) ───────────────


def _extract_mermaid_pre(html: str) -> str:
    start = html.find('<pre class="mermaid">') + len('<pre class="mermaid">')
    end = html.find("</pre>", start)
    assert start > len('<pre class="mermaid">') - 1, "no <pre class='mermaid'> found"
    return html[start:end]


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


@pytest.mark.skipif(MMDC_AVAILABLE, reason="mmdc present — uses SVG path, not <pre>")
def test_config_frontmatter_preserved_in_pre():
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_XYCHART_MD)
    pre = _extract_mermaid_pre(html)
    assert "---" in pre
    assert "config:" in pre
    assert "xyChart:" in pre
    assert "xAxis:" in pre
    assert "labelRotation: 20" in pre, "labelRotation value lost or corrupted"


@pytest.mark.skipif(MMDC_AVAILABLE, reason="mmdc present — uses SVG path, not <pre>")
def test_config_yaml_keys_not_html_escaped():
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_XYCHART_MD)
    pre = _extract_mermaid_pre(html)
    assert "      labelRotation: 20" in pre


@pytest.mark.skipif(MMDC_AVAILABLE, reason="mmdc present — uses SVG path, not <pre>")
def test_diagram_body_quotes_are_escaped_but_decodable():
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_XYCHART_MD)
    pre = _extract_mermaid_pre(html)
    assert "&quot;Drift&quot;" in pre
    assert "labelRotation: 20" in pre


@pytest.mark.skipif(MMDC_AVAILABLE, reason="mmdc present — uses SVG path, not <pre>")
def test_pre_block_byte_length_matches_expected_range():
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_XYCHART_MD)
    pre = _extract_mermaid_pre(html)
    assert 180 < len(pre) < 400, f"<pre> block length {len(pre)} outside expected range"


# ── 7. Mermaid directive syntax %%{init: ...}%% ──────────────────────────────
# The %%{init: {...}}%% directive is the Mermaid inline config syntax used in
# GitLab Flavored Markdown (GLFM).  It differs from the YAML ---config:---
# frontmatter tested above: the directive is placed as the very first line of
# the mermaid fence.
#
# Fixture source: https://stackoverflow.com/a/66751560
# The key invariants for both rendering paths:
#   - %% characters must not be HTML-escaped or silently dropped.
#   - The directive content (init key + options) must be preserved intact.
#   - The diagram body (graph nodes and edges) must also be preserved.

_DIRECTIVE_MD = """\
```mermaid
%%{init: {'theme': 'forest'}}%%
graph TD
  A[Christmas] -->|Get money| B(Go shopping)
  B --> C{Let me think}
  C -->|One| D[Laptop]
  C -->|Two| E[iPhone]
  C -->|Three| F[Car]
```
"""


def test_directive_fixture_file_exists():
    """The mermaid_directive.md fixture must be loadable."""
    assert DIRECTIVE_FIXTURE_PATH.exists(), "fixture file missing"
    assert "%%{init:" in DIRECTIVE_FIXTURE_MD, "directive syntax not in fixture"
    assert "graph TD" in DIRECTIVE_FIXTURE_MD, "diagram body not in fixture"


def test_directive_fixture_renders_without_crash():
    """The directive fixture must render without raising."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(DIRECTIVE_FIXTURE_MD)
    assert isinstance(html, str) and html.strip()


def test_directive_inline_md_renders_without_crash():
    """The inline directive Markdown string must render without raising."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_DIRECTIVE_MD)
    assert isinstance(html, str) and html.strip()


def test_directive_no_raw_fence_in_output():
    """The ```mermaid fence must not appear literally in the output."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_DIRECTIVE_MD)
    assert "```mermaid" not in html, "raw mermaid fence leaked into output"


@pytest.mark.skipif(MMDC_AVAILABLE, reason="mmdc present — browser-side path not used")
def test_directive_percent_signs_not_html_escaped():
    """The %% delimiter must survive html.escape() intact inside <pre>."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_DIRECTIVE_MD)
    pre = _extract_mermaid_pre(html)
    assert "%%{init:" in pre, (
        "%% directive start was HTML-escaped or dropped; "
        f"actual pre content: {pre[:120]!r}"
    )
    assert "}%%" in pre, "%% directive end marker lost"


@pytest.mark.skipif(MMDC_AVAILABLE, reason="mmdc present — browser-side path not used")
def test_directive_theme_value_preserved_in_pre():
    """The theme value 'forest' must be present inside the <pre> block."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_DIRECTIVE_MD)
    pre = _extract_mermaid_pre(html)
    assert "forest" in pre, f"theme value lost; pre: {pre[:120]!r}"


@pytest.mark.skipif(MMDC_AVAILABLE, reason="mmdc present — browser-side path not used")
def test_directive_graph_nodes_preserved_in_pre():
    """Graph node labels must be present inside the <pre> block."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_DIRECTIVE_MD)
    pre = _extract_mermaid_pre(html)
    assert "Christmas" in pre
    assert "Laptop" in pre
    assert "iPhone" in pre
    assert "Car" in pre


@pytest.mark.skipif(MMDC_AVAILABLE, reason="mmdc present — browser-side path not used")
def test_directive_graph_keyword_present_in_pre():
    """'graph TD' keyword must be present (diagram type declaration)."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_DIRECTIVE_MD)
    pre = _extract_mermaid_pre(html)
    assert "graph TD" in pre


@pytest.mark.skipif(MMDC_AVAILABLE, reason="mmdc present — browser-side path not used")
def test_directive_arrows_escaped_not_dropped():
    """Arrow syntax --> must be HTML-escaped as --&gt; but not dropped."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_DIRECTIVE_MD)
    pre = _extract_mermaid_pre(html)
    assert "--&gt;" in pre, "arrow --> was dropped rather than HTML-escaped"
    assert "-->" not in pre, "unescaped --> will confuse the HTML parser"


@pytest.mark.skipif(MMDC_AVAILABLE, reason="mmdc present — browser-side path not used")
def test_directive_pre_block_byte_length_canary():
    """Pin the byte length of the <pre> block as a corruption canary.

    If this value changes unexpectedly, the directive or graph content has
    been silently dropped, duplicated, or re-encoded.  Update the expected
    range only after confirming the content is correct.
    """
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_DIRECTIVE_MD)
    pre = _extract_mermaid_pre(html)
    assert 150 < len(pre) < 350, (
        f"<pre> block is {len(pre)} bytes — outside expected 150–350 byte range. "
        "Directive or graph content may have been corrupted."
    )


@pytest.mark.skipif(not MMDC_AVAILABLE, reason="mmdc not installed")
def test_directive_mmdc_path_produces_svg():
    """With mmdc, the directive fixture must produce an SVG data URI."""
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_DIRECTIVE_MD)
    assert "data:image/svg+xml;base64," in html, "no SVG from mmdc for directive diagram"
    assert '<pre class="mermaid">' not in html


@pytest.mark.skipif(not MMDC_AVAILABLE, reason="mmdc not installed")
def test_directive_mmdc_path_svg_non_trivial():
    """The SVG produced by mmdc for the directive diagram must be non-trivial."""
    import base64
    import re
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_DIRECTIVE_MD)
    match = re.search(r"data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)", html)
    assert match, "no SVG data URI found"
    svg = base64.b64decode(match.group(1)).decode("utf-8", errors="replace")
    assert len(svg) > 2000, f"SVG only {len(svg)} bytes — may be a placeholder"
    assert "<svg" in svg, "data URI is not an SVG"


@pytest.mark.skipif(not MMDC_AVAILABLE, reason="mmdc not installed")
def test_directive_mmdc_path_svg_contains_graph_content():
    """The rendered SVG must contain content from the flowchart nodes."""
    import base64
    import re
    from calamus.renderer import MistuneRenderer

    html = MistuneRenderer().render(_DIRECTIVE_MD)
    match = re.search(r"data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)", html)
    assert match
    svg = base64.b64decode(match.group(1)).decode("utf-8", errors="replace")
    # At least one node label must appear in the rendered SVG
    node_labels = ["Christmas", "shopping", "Laptop", "iPhone", "Car"]
    assert any(label in svg for label in node_labels), (
        f"No graph node labels found in SVG. Present: {svg[:300]!r}"
    )

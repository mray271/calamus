"""Tests for mermaid_support module."""

import re
import shutil
from urllib.parse import urlparse


def script_src_hosts(html: str) -> set[str]:
    """Extract hostnames from script src attributes."""
    sources = re.findall(r'<script[^>]*\ssrc="([^"]+)"', html)
    return {urlparse(source).netloc for source in sources}


def test_extract_mermaid_blocks_finds_blocks():
    from calamus.mermaid_support import extract_mermaid_blocks

    text = "Hello\n```mermaid\ngraph TD\nA-->B\n```\nWorld"
    blocks = extract_mermaid_blocks(text)
    assert len(blocks) == 1
    assert "graph TD" in blocks[0][1]


def test_extract_mermaid_blocks_empty():
    from calamus.mermaid_support import extract_mermaid_blocks

    assert extract_mermaid_blocks("no diagrams here") == []


def test_extract_multiple_blocks():
    from calamus.mermaid_support import extract_mermaid_blocks

    text = "```mermaid\nA-->B\n```\ntext\n```mermaid\nC-->D\n```"
    blocks = extract_mermaid_blocks(text)
    assert len(blocks) == 2


def test_extract_returns_positions():
    from calamus.mermaid_support import extract_mermaid_blocks

    text = "prefix\n```mermaid\ngraph TD\nA-->B\n```"
    blocks = extract_mermaid_blocks(text)
    assert len(blocks) == 1
    pos, src = blocks[0]
    assert isinstance(pos, int)
    assert pos >= 0


def test_fallback_renderer_is_available():
    from calamus.mermaid_support import FallbackMermaidRenderer

    renderer = FallbackMermaidRenderer()
    assert renderer.is_available() is True


def test_fallback_renderer_returns_svg():
    from calamus.mermaid_support import FallbackMermaidRenderer

    renderer = FallbackMermaidRenderer()
    svg = renderer.render_to_svg("graph TD\nA-->B")
    assert svg is not None
    assert "<svg" in svg


def test_fallback_renderer_escapes_html_in_source():
    from calamus.mermaid_support import FallbackMermaidRenderer

    renderer = FallbackMermaidRenderer()
    svg = renderer.render_to_svg("<script>alert('xss')</script>")
    assert "<script>" not in svg


def test_subprocess_renderer_unavailable_when_no_mmdc(monkeypatch):
    """SubprocessMermaidRenderer.is_available() returns False when mmdc is not on PATH."""
    monkeypatch.setattr(shutil, "which", lambda _: None)
    from calamus.mermaid_support import SubprocessMermaidRenderer

    monkeypatch.setattr(SubprocessMermaidRenderer, "_mmdc_available", None)
    from calamus.mermaid_support import SubprocessMermaidRenderer

    renderer = SubprocessMermaidRenderer()
    assert renderer.is_available() is False


def test_subprocess_renderer_render_returns_none_when_unavailable(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    from calamus.mermaid_support import SubprocessMermaidRenderer

    monkeypatch.setattr(SubprocessMermaidRenderer, "_mmdc_available", None)
    from calamus.mermaid_support import SubprocessMermaidRenderer

    renderer = SubprocessMermaidRenderer()
    result = renderer.render_to_svg("graph TD\nA-->B")
    assert result is None


def test_get_best_renderer_returns_fallback_when_no_mmdc(monkeypatch):
    from calamus.mermaid_support import (
        MermaidxRenderer,
        SubprocessMermaidRenderer,
        FallbackMermaidRenderer,
        get_best_renderer,
    )

    # Mock both mermaidx and mmdc to be unavailable
    monkeypatch.setattr(MermaidxRenderer, "_mermaidx_available", False)
    monkeypatch.setattr(SubprocessMermaidRenderer, "_mmdc_available", False)

    renderer = get_best_renderer()
    assert isinstance(renderer, FallbackMermaidRenderer)


def test_get_best_renderer_prefers_mermaidx_when_available(monkeypatch):
    from calamus.mermaid_support import MermaidxRenderer, get_best_renderer

    # Reset cache so it re-checks availability
    monkeypatch.setattr(MermaidxRenderer, "_mermaidx_available", None)

    renderer = get_best_renderer()
    # mermaidx should be available in the test environment (it's a dependency)
    assert isinstance(renderer, MermaidxRenderer)


def test_get_best_renderer_returns_subprocess_when_only_mmdc_available(monkeypatch):
    from calamus.mermaid_support import (
        MermaidxRenderer,
        SubprocessMermaidRenderer,
        get_best_renderer,
    )

    # Make mermaidx unavailable but mmdc available
    monkeypatch.setattr(MermaidxRenderer, "_mermaidx_available", False)
    monkeypatch.setattr(SubprocessMermaidRenderer, "_mmdc_available", True)

    renderer = get_best_renderer()
    assert isinstance(renderer, SubprocessMermaidRenderer)


def test_get_best_renderer_returns_renderer():
    from calamus.mermaid_support import AbstractMermaidRenderer, get_best_renderer

    renderer = get_best_renderer()
    assert isinstance(renderer, AbstractMermaidRenderer)
    assert renderer.is_available() is True


def test_mermaid_version_constant():
    from calamus.mermaid_support import MERMAID_VERSION

    assert MERMAID_VERSION == "11.5.0"


def test_mermaid_html_labels_setting_roundtrip():
    from calamus.mermaid_support import (
        get_mermaid_html_labels,
        set_mermaid_html_labels,
    )

    original = get_mermaid_html_labels()
    try:
        set_mermaid_html_labels(False)
        assert get_mermaid_html_labels() is False
        set_mermaid_html_labels(True)
        assert get_mermaid_html_labels() is True
    finally:
        set_mermaid_html_labels(original)


def test_mermaid_cdn_url_contains_version():
    from calamus.mermaid_support import MERMAID_CDN_URL, MERMAID_VERSION

    assert MERMAID_VERSION in MERMAID_CDN_URL
    assert "jsdelivr" in MERMAID_CDN_URL


def test_get_mermaid_script_tag_cdn_fallback():
    from calamus.mermaid_support import get_mermaid_script_tag

    tag = get_mermaid_script_tag(local_first=False)
    assert "<script" in tag
    assert "mermaid" in tag


def test_get_mermaid_script_tag_local_missing_falls_back_to_cdn(tmp_path, monkeypatch):
    """When local file does not exist, should fall back to CDN URL."""
    import calamus.mermaid_support as ms

    monkeypatch.setattr(ms, "MERMAID_LOCAL_PATH", str(tmp_path / "nonexistent.js"))
    monkeypatch.setattr(
        ms, "MERMAID_SYSTEM_PATH", str(tmp_path / "nonexistent_system.js")
    )
    tag = ms.get_mermaid_script_tag(local_first=True)
    hosts = script_src_hosts(tag)
    assert any(host == "cdn.jsdelivr.net" for host in hosts)


def test_get_mermaid_script_tag_local_file_preferred(tmp_path, monkeypatch):
    """When local file exists, its content is inlined instead of using the CDN."""
    import calamus.mermaid_support as ms

    local = tmp_path / "mermaid.min.js"
    local.write_text("// fake mermaid")
    monkeypatch.setattr(ms, "MERMAID_LOCAL_PATH", str(local))
    tag = ms.get_mermaid_script_tag(local_first=True)
    assert "// fake mermaid" in tag
    assert "cdn.jsdelivr.net" not in tag


def test_get_mermaid_init_script():
    from calamus.mermaid_support import get_mermaid_init_script

    script = get_mermaid_init_script()
    assert "<script>" in script or "<script" in script
    assert "mermaid.initialize" in script
    assert "startOnLoad" in script


def test_preprocess_replaces_mermaid_blocks():
    from calamus.mermaid_support import preprocess_markdown_for_static_export

    text = "Before\n```mermaid\ngraph TD\nA-->B\n```\nAfter"
    result = preprocess_markdown_for_static_export(text)
    assert "```mermaid" not in result
    assert "After" in result
    assert "Before" in result


def test_preprocess_result_contains_image_tag():
    from calamus.mermaid_support import preprocess_markdown_for_static_export

    text = "```mermaid\ngraph TD\nA-->B\n```"
    result = preprocess_markdown_for_static_export(text)
    assert "<img" in result
    assert "data:image/svg+xml;base64," in result


def test_preprocess_no_mermaid_unchanged():
    from calamus.mermaid_support import preprocess_markdown_for_static_export

    text = "# Just markdown\n\nNo diagrams here."
    result = preprocess_markdown_for_static_export(text)
    assert result == text


def test_preprocess_multiple_blocks():
    from calamus.mermaid_support import preprocess_markdown_for_static_export

    text = "```mermaid\ngraph TD\nA-->B\n```\nMiddle\n```mermaid\nsequenceDiagram\nA->>B: Hi\n```"
    result = preprocess_markdown_for_static_export(text)
    assert "```mermaid" not in result
    assert "Middle" in result
    assert result.count("<img") == 2


# ---------------------------------------------------------------------------
# MermaidCache
# ---------------------------------------------------------------------------


def test_mermaid_cache_put_and_get():
    from calamus.mermaid_support import MermaidCache

    cache = MermaidCache()
    cache.put("graph TD\nA-->B", "<svg>test</svg>")
    assert cache.get("graph TD\nA-->B") == "<svg>test</svg>"


def test_mermaid_cache_miss_returns_none():
    from calamus.mermaid_support import MermaidCache

    cache = MermaidCache()
    assert cache.get("nonexistent diagram") is None


def test_mermaid_cache_has_returns_false_before_put():
    from calamus.mermaid_support import MermaidCache

    cache = MermaidCache()
    assert cache.has("anything") is False


def test_mermaid_cache_has_returns_true_after_put():
    from calamus.mermaid_support import MermaidCache

    cache = MermaidCache()
    cache.put("diagram source", "<svg/>")
    assert cache.has("diagram source") is True


def test_mermaid_cache_stores_multiple_entries_independently():
    from calamus.mermaid_support import MermaidCache

    cache = MermaidCache()
    cache.put("A", "<svg>A</svg>")
    cache.put("B", "<svg>B</svg>")
    assert cache.get("A") == "<svg>A</svg>"
    assert cache.get("B") == "<svg>B</svg>"


# ---------------------------------------------------------------------------
# preprocess_with_cache
# ---------------------------------------------------------------------------


def test_preprocess_with_cache_hit_returns_img_tag():
    from calamus.mermaid_support import MermaidCache, preprocess_with_cache

    cache = MermaidCache()
    diagram = "graph TD\nA-->B"
    cache.put(diagram, "<svg>cached</svg>")
    result = preprocess_with_cache(f"```mermaid\n{diagram}\n```", cache)
    assert "<img" in result
    assert "data:image/svg+xml;base64," in result
    assert "```mermaid" not in result


def test_preprocess_with_cache_miss_returns_pre_mermaid():
    from calamus.mermaid_support import MermaidCache, preprocess_with_cache

    cache = MermaidCache()
    result = preprocess_with_cache("```mermaid\ngraph TD\nA-->B\n```", cache)
    assert '<pre class="mermaid">' in result
    assert "```mermaid" not in result


def test_preprocess_with_cache_passthrough_when_no_blocks():
    from calamus.mermaid_support import MermaidCache, preprocess_with_cache

    cache = MermaidCache()
    text = "# Just markdown\nNo diagrams."
    assert preprocess_with_cache(text, cache) == text


def test_preprocess_with_cache_ignores_mermaid_inside_outer_fence():
    """Mermaid blocks nested inside a ````markdown outer fence are left as-is."""
    from calamus.mermaid_support import MermaidCache, preprocess_with_cache

    cache = MermaidCache()
    diagram = "graph LR\nA --> B"
    cache.put(diagram, "<svg>cached</svg>")
    # The ```mermaid fence is inside a ````markdown outer fence.
    text = "````markdown\n```mermaid\n{}\n```\n````".format(diagram)
    result = preprocess_with_cache(text, cache)
    assert "```mermaid" in result
    assert "<img" not in result
    assert '<pre class="mermaid">' not in result


def test_extract_mermaid_blocks_ignores_nested_in_outer_fence():
    """extract_mermaid_blocks skips blocks nested inside an outer fence."""
    from calamus.mermaid_support import extract_mermaid_blocks

    text = "````markdown\n```mermaid\ngraph TD\nA-->B\n```\n````"
    assert extract_mermaid_blocks(text) == []


def test_preprocess_static_export_ignores_mermaid_inside_outer_fence(monkeypatch):
    """preprocess_markdown_for_static_export leaves nested mermaid blocks untouched."""
    import calamus.mermaid_support as ms

    monkeypatch.setattr(ms.SubprocessMermaidRenderer, "_mmdc_available", False)
    diagram = "graph LR\nA --> B"
    text = "````markdown\n```mermaid\n{}\n```\n````".format(diagram)
    result = ms.preprocess_markdown_for_static_export(text)
    assert "```mermaid" in result
    assert "<img" not in result


# ---------------------------------------------------------------------------
# SubprocessMermaidRenderer — output file not created
# ---------------------------------------------------------------------------


def test_subprocess_renderer_returns_none_when_output_not_created(monkeypatch):
    """render_to_svg returns None when subprocess succeeds but creates no output file."""
    import subprocess

    from calamus.mermaid_support import SubprocessMermaidRenderer

    monkeypatch.setattr(SubprocessMermaidRenderer, "_mmdc_available", None)
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/mmdc")

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    renderer = SubprocessMermaidRenderer()
    assert renderer.render_to_svg("graph TD\nA-->B") is None


def test_subprocess_renderer_writes_html_labels_from_preference(monkeypatch):
    """mmdc config should reflect the mermaid_html_labels preference."""
    import json
    import subprocess

    from calamus.mermaid_support import (
        SubprocessMermaidRenderer,
        set_mermaid_html_labels,
    )

    monkeypatch.setattr(SubprocessMermaidRenderer, "_mmdc_available", None)
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/mmdc")

    captured = {}

    def fake_run(cmd, **kwargs):
        cfg_path = cmd[cmd.index("-c") + 1]
        out_path = cmd[cmd.index("-o") + 1]
        captured["config"] = json.loads(open(cfg_path, encoding="utf-8").read())
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write("<svg/>")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    from calamus.mermaid_support import get_mermaid_html_labels

    original = get_mermaid_html_labels()
    try:
        # First check disabled mode.
        set_mermaid_html_labels(False)
        renderer = SubprocessMermaidRenderer()
        assert renderer.render_to_svg("graph TD\nA-->B") == "<svg/>"
        assert captured["config"]["htmlLabels"] is False
        assert captured["config"]["flowchart"]["htmlLabels"] is False

        # Then check enabled mode.
        set_mermaid_html_labels(True)
        renderer = SubprocessMermaidRenderer()
        assert renderer.render_to_svg("graph TD\nA-->B") == "<svg/>"
        assert captured["config"]["htmlLabels"] is True
        assert captured["config"]["flowchart"]["htmlLabels"] is True
    finally:
        set_mermaid_html_labels(original)

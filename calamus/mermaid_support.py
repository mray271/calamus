"""Mermaid diagram support utilities."""

from __future__ import annotations

from abc import ABC, abstractmethod
import base64
import hashlib
import html
from pathlib import Path
import re
import shutil
import subprocess
import threading

MERMAID_VERSION = "11.5.0"
MERMAID_CDN_URL = (
    f"https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VERSION}/dist/mermaid.min.js"
)
MERMAID_LOCAL_PATH = "calamus/resources/js/mermaid.min.js"
# System-wide copy baked into the Docker image (outside the volume-mounted /app).
# Used as a fallback when the volume mount shadows the source-tree copy.
MERMAID_SYSTEM_PATH = "/usr/local/share/calamus/js/mermaid.min.js"
# Puppeteer config for mmdc inside Docker (no-sandbox, system Chromium).
MMDC_PUPPETEER_CONFIG = "/usr/local/share/calamus/mmdc-puppeteer.json"


def get_mermaid_script_tag(local_first: bool = True) -> str:
    """Return a <script> tag that loads Mermaid.js.

    When a local copy is available the JS is inlined directly into the tag
    so WebKit's file:// security restrictions cannot block it.
    """
    if local_first:
        for candidate in (
            Path(MERMAID_LOCAL_PATH).resolve(),
            Path(MERMAID_SYSTEM_PATH),
        ):
            if candidate.exists():
                js = candidate.read_text(encoding="utf-8")
                return f"<script>{js}</script>"
    return f'<script src="{MERMAID_CDN_URL}"></script>'


def get_mermaid_init_script() -> str:
    """Return the mermaid.initialize({...}) script block."""
    return """
    <script>
      document.addEventListener('DOMContentLoaded', function() {
        mermaid.initialize({ startOnLoad: true, theme: 'default' });
      });
    </script>
    """


def extract_mermaid_blocks(markdown_text: str) -> list[tuple[int, str]]:
    """Find all Mermaid fenced code blocks."""
    pattern = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)
    return [
        (match.start(), match.group(1).strip())
        for match in pattern.finditer(markdown_text)
    ]


class AbstractMermaidRenderer(ABC):
    """Renders Mermaid diagram source to SVG string."""

    @abstractmethod
    def render_to_svg(self, diagram_source: str) -> str | None:
        """Return SVG string or None if rendering failed."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether this renderer can be used."""


class SubprocessMermaidRenderer(AbstractMermaidRenderer):
    """Renders Mermaid diagrams using mermaid-cli."""

    _mmdc_available: bool | None = None  # class-level cache; set once per process

    def is_available(self) -> bool:
        if SubprocessMermaidRenderer._mmdc_available is None:
            SubprocessMermaidRenderer._mmdc_available = shutil.which("mmdc") is not None
        return SubprocessMermaidRenderer._mmdc_available

    def render_to_svg(self, diagram_source: str) -> str | None:
        if not self.is_available():
            return None
        work_dir = Path("calamus/resources/.mermaid-render")
        work_dir.mkdir(parents=True, exist_ok=True)
        input_path = work_dir / "diagram.mmd"
        output_path = work_dir / "diagram.svg"
        input_path.write_text(diagram_source, encoding="utf-8")
        try:
            puppeteer_config = Path(MMDC_PUPPETEER_CONFIG)
            subprocess.run(
                [
                    "mmdc",
                    "-i",
                    str(input_path),
                    "-o",
                    str(output_path),
                    *(
                        ["-p", str(puppeteer_config)]
                        if puppeteer_config.exists()
                        else []
                    ),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if output_path.exists():
                return output_path.read_text(encoding="utf-8")
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None
        finally:
            for path in (input_path, output_path):
                if path.exists():
                    path.unlink()
        return None


class FallbackMermaidRenderer(AbstractMermaidRenderer):
    """Returns a placeholder SVG when Mermaid CLI is unavailable."""

    def is_available(self) -> bool:
        return True

    def render_to_svg(self, diagram_source: str) -> str | None:
        escaped = html.escape(diagram_source)
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="200">'
            '<rect width="100%" height="100%" fill="#f8f8f8" stroke="#cccccc"/>'
            '<text x="20" y="40" font-family="monospace" font-size="16">'
            f"{escaped}"
            "</text>"
            "</svg>"
        )


def get_best_renderer() -> AbstractMermaidRenderer:
    """Return the best available Mermaid renderer."""
    renderer = SubprocessMermaidRenderer()
    if renderer.is_available():
        return renderer
    return FallbackMermaidRenderer()


class MermaidCache:
    """Thread-safe cache mapping Mermaid diagram source → rendered SVG string."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(source: str) -> str:
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def get(self, source: str) -> str | None:
        with self._lock:
            return self._cache.get(self._key(source))

    def put(self, source: str, svg: str) -> None:
        with self._lock:
            self._cache[self._key(source)] = svg

    def has(self, source: str) -> bool:
        return self.get(source) is not None


def preprocess_with_cache(markdown_text: str, cache: MermaidCache) -> str:
    """Replace Mermaid fenced blocks using the SVG cache.

    Blocks present in *cache* are replaced with inline ``<img>`` data URIs
    (same format as :func:`preprocess_markdown_for_static_export`).  Blocks
    not yet cached are replaced with ``<pre class="mermaid">`` so the
    browser-side mermaid.js can render them as a fallback while the
    background thread computes the SVG.
    """
    pattern = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)

    def repl(match: re.Match[str]) -> str:
        diagram_source = match.group(1).strip()
        svg = cache.get(diagram_source)
        if svg is not None:
            encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
            return (
                f'\n<img alt="Mermaid diagram" '
                f'src="data:image/svg+xml;base64,{encoded}" />\n'
            )
        escaped = html.escape(diagram_source)
        return f'\n<pre class="mermaid">{escaped}</pre>\n'

    return pattern.sub(repl, markdown_text)


def preprocess_markdown_for_static_export(markdown_text: str) -> str:
    """Replace Mermaid fenced blocks with inline SVG data URIs."""
    renderer = get_best_renderer()
    pattern = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)

    def repl(match: re.Match[str]) -> str:
        diagram_source = match.group(1).strip()
        svg = renderer.render_to_svg(diagram_source) or ""
        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return f'\n<img alt="Mermaid diagram" src="data:image/svg+xml;base64,{encoded}" />\n'

    return pattern.sub(repl, markdown_text)

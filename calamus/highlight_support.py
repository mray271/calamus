"""highlight.js support — code syntax highlighting in the HTML preview."""

from __future__ import annotations

from pathlib import Path

HIGHLIGHT_VERSION = "11.9.0"
HIGHLIGHT_CDN_JS = (
    f"https://cdnjs.cloudflare.com/ajax/libs/highlight.js/"
    f"{HIGHLIGHT_VERSION}/highlight.min.js"
)
HIGHLIGHT_CDN_CSS_LIGHT = (
    f"https://cdnjs.cloudflare.com/ajax/libs/highlight.js/"
    f"{HIGHLIGHT_VERSION}/styles/github.min.css"
)
HIGHLIGHT_CDN_CSS_DARK = (
    f"https://cdnjs.cloudflare.com/ajax/libs/highlight.js/"
    f"{HIGHLIGHT_VERSION}/styles/github-dark.min.css"
)

_LOCAL_JS = Path(__file__).parent / "resources" / "js" / "highlight.min.js"
_LOCAL_CSS_LIGHT = (
    Path(__file__).parent / "resources" / "css" / "highlight-github.min.css"
)
_LOCAL_CSS_DARK = (
    Path(__file__).parent / "resources" / "css" / "highlight-github-dark.min.css"
)
_SYSTEM_JS = Path("/usr/local/share/calamus/js/highlight.min.js")
_SYSTEM_CSS_LIGHT = Path("/usr/local/share/calamus/css/highlight-github.min.css")
_SYSTEM_CSS_DARK = Path("/usr/local/share/calamus/css/highlight-github-dark.min.css")


def _read_local(primary: Path, fallback: Path) -> str | None:
    for path in (primary, fallback):
        if path.exists():
            return path.read_text(encoding="utf-8")
    return None


def get_highlight_script_tag() -> str:
    """Return a ``<script>`` tag that loads highlight.js.

    Inlines the JS when a local copy is available so WebKit's ``file://``
    security policy cannot block it.  Falls back to CDN when offline or in
    environments without the bundled copy.
    """
    js = _read_local(_LOCAL_JS, _SYSTEM_JS)
    if js:
        return f"<script>{js}</script>"
    return f'<script src="{HIGHLIGHT_CDN_JS}"></script>'


def get_highlight_css_tag(dark: bool = False) -> str:
    """Return a ``<style>`` tag with the highlight.js theme CSS.

    Uses the GitHub theme for light mode and GitHub Dark for dark mode.
    Inlines the CSS so WebKit's ``file://`` policy cannot block it.
    """
    if dark:
        css = _read_local(_LOCAL_CSS_DARK, _SYSTEM_CSS_DARK)
        fallback_url = HIGHLIGHT_CDN_CSS_DARK
    else:
        css = _read_local(_LOCAL_CSS_LIGHT, _SYSTEM_CSS_LIGHT)
        fallback_url = HIGHLIGHT_CDN_CSS_LIGHT

    if css:
        return f"<style>{css}</style>"
    return f'<link rel="stylesheet" href="{fallback_url}">'

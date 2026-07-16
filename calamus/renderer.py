"""Markdown renderer abstractions and concrete implementations."""

from __future__ import annotations

import html
import re
import unicodedata
from abc import ABC, abstractmethod

import mistune

from calamus import MERMAID_VERSION


def _slugify(text: str) -> str:
    """Convert heading text to a GitHub-style anchor id."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    return text


_HEADING_RE = re.compile(r"(<h([1-6])>)(.*?)(</h[1-6]>)", re.DOTALL)
_HEADING_WITH_ID_RE = re.compile(
    r"<h([1-6])[^>]*\sid=\"([^\"]+)\"[^>]*>(.*?)</h\1>",
    re.DOTALL,
)
_BLOCKQUOTE_RE = re.compile(r"<blockquote>\s*(.*?)\s*</blockquote>", re.DOTALL)
_FIRST_PARAGRAPH_RE = re.compile(r"\s*<p>(.*?)</p>", re.DOTALL)
_ALERT_MARKER_RE = re.compile(
    r"^\[!(note|tip|important|caution|warning)\](?:[ \t]+(.+))?$",
    re.IGNORECASE,
)
_ALERT_DEFAULT_TITLES = {
    "note": "Note",
    "tip": "Tip",
    "important": "Important",
    "caution": "Caution",
    "warning": "Warning",
}
_TEXT_OR_TAG_RE = re.compile(r"(<[^>]+>|[^<]+)")
_TAG_NAME_RE = re.compile(r"^</?\s*([a-zA-Z0-9]+)")
_WWW_URL_RE = re.compile(
    r"(?<![\w@])" r"(www\.[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}(?:/[^\s<]*)?)"
)
_EMAIL_RE = re.compile(
    r"(?<![\w.+-])" r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})" r"(?![\w@])"
)
_LINKIFY_EXCLUDED_TAGS = {"a", "code", "pre", "script", "style"}
_TRAILING_PUNCTUATION = ".,:;!?)"
_GLFM_TOC_MARKER_RE = re.compile(
    r"<p>\s*\[\[\s*<em>\s*toc\s*</em>\s*\]\]\s*</p>",
    re.IGNORECASE,
)
_GLFM_COLOR_HEX_RE = re.compile(
    r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$"
)
_RGB_CHANNEL_RE = (
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d|" r"(?:100(?:\.0+)?|[1-9]?\d(?:\.\d+)?)%)"
)
_HSL_PERCENT_RE = r"(?:100(?:\.0+)?|[1-9]?\d(?:\.\d+)?)%"
_HUE_RE = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"
_ALPHA_RE = r"(?:0(?:\.\d+)?|1(?:\.0+)?|\.\d+)"
_GLFM_COLOR_FUNCTION_RE = re.compile(
    r"^(?:"
    rf"rgb\(\s*{_RGB_CHANNEL_RE}\s*,\s*{_RGB_CHANNEL_RE}\s*,\s*{_RGB_CHANNEL_RE}\s*\)"
    r"|"
    rf"rgba\(\s*{_RGB_CHANNEL_RE}\s*,\s*{_RGB_CHANNEL_RE}\s*,\s*{_RGB_CHANNEL_RE}\s*,\s*{_ALPHA_RE}\s*\)"
    r"|"
    rf"hsl\(\s*{_HUE_RE}\s*,\s*{_HSL_PERCENT_RE}\s*,\s*{_HSL_PERCENT_RE}\s*\)"
    r"|"
    rf"hsla\(\s*{_HUE_RE}\s*,\s*{_HSL_PERCENT_RE}\s*,\s*{_HSL_PERCENT_RE}\s*,\s*{_ALPHA_RE}\s*\)"
    r")$",
    re.IGNORECASE,
)
_EMOJI_SHORTCODE_RE = re.compile(r":([a-z0-9+\-][a-z0-9_+\-]*):", re.IGNORECASE)
_EMOJI_EXCLUDED_TAGS = {"code", "pre", "script", "style"}
_ADJACENT_FOOTNOTE_SUP_RE = re.compile(
    r"(</a>)\s*(</sup>)\s*(?=<sup class=\"footnote-ref\")"
)
_FOOTNOTE_SUP_OPEN = '<sup class="footnote-ref"'
_FOOTNOTE_SUP_CLOSE = "</sup>"
_PUNCTUATION_AFTER_FOOTNOTES = ".,;:!?"
# Curated local subset of GitLab/Tanuki emoji shortcodes.
# To add support for a new request, append shortcode -> Unicode entries here
# (include common aliases when relevant), keep unknown shortcodes as literals,
# and update tests in tests/test_glfm_compat.py and tests/test_renderer.py.
_GLFM_EMOJI_SHORTCODES = {
    "+1": "👍",
    "-1": "👎",
    "100": "💯",
    "angry": "😠",
    "blush": "😊",
    "bug": "🐛",
    "calendar": "📆",
    "checkered_flag": "🏁",
    "clap": "👏",
    "confused": "😕",
    "cry": "😢",
    "eyes": "👀",
    "fire": "🔥",
    "grin": "😁",
    "grinning": "😀",
    "heart": "❤️",
    "heart_eyes": "😍",
    "heavy_check_mark": "✔️",
    "hourglass": "⌛",
    "joy": "😂",
    "laughing": "😆",
    "link": "🔗",
    "mag": "🔍",
    "memo": "📝",
    "minus1": "👎",
    "no_entry_sign": "🚫",
    "ok_hand": "👌",
    "open_file_folder": "📂",
    "pencil2": "✏️",
    "point_up": "☝️",
    "question": "❓",
    "rocket": "🚀",
    "see_no_evil": "🙈",
    "smile": "😄",
    "sparkles": "✨",
    "star": "⭐",
    "sunglasses": "😎",
    "tada": "🎉",
    "thinking": "🤔",
    "thumbsup": "👍",
    "thumbsdown": "👎",
    "triangular_flag_on_post": "🚩",
    "warning": "⚠️",
    "wave": "👋",
    "white_check_mark": "✅",
    "x": "❌",
}


def _add_heading_ids(html_text: str) -> str:
    """Post-process rendered HTML to add id attributes to headings."""
    if not isinstance(html_text, str):
        return html_text

    def _repl(m: re.Match) -> str:
        open_tag, level, inner, close_tag = (
            m.group(1),
            m.group(2),
            m.group(3),
            m.group(4),
        )
        plain = re.sub(r"<[^>]+>", "", inner)
        slug = _slugify(plain)
        if slug:
            return f'<h{level} id="{slug}">{inner}{close_tag}'
        return m.group(0)

    return _HEADING_RE.sub(_repl, html_text)


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def _split_trailing_punctuation(text: str) -> tuple[str, str]:
    trimmed = text
    trailing = ""
    while trimmed and trimmed[-1] in _TRAILING_PUNCTUATION:
        trailing = trimmed[-1] + trailing
        trimmed = trimmed[:-1]
    return trimmed, trailing


def _linkify_plain_text_segment(text: str) -> str:
    def _www_repl(match: re.Match[str]) -> str:
        raw = match.group(1)
        url_text, trailing = _split_trailing_punctuation(raw)
        if not url_text:
            return raw
        href = html.escape(f"https://{html.unescape(url_text)}", quote=True)
        return f'<a href="{href}">{url_text}</a>{trailing}'

    def _email_repl(match: re.Match[str]) -> str:
        raw = match.group(1)
        email_text, trailing = _split_trailing_punctuation(raw)
        if not email_text:
            return raw
        href = html.escape(f"mailto:{html.unescape(email_text)}", quote=True)
        return f'<a href="{href}">{email_text}</a>{trailing}'

    text = _WWW_URL_RE.sub(_www_repl, text)
    return _EMAIL_RE.sub(_email_repl, text)


def _linkify_extended_autolinks(html_text: str) -> str:
    """Linkify GFM extended autolinks (www. URLs and bare emails)."""
    if not isinstance(html_text, str):
        return html_text

    open_counts = {tag: 0 for tag in _LINKIFY_EXCLUDED_TAGS}
    chunks: list[str] = []

    for token in _TEXT_OR_TAG_RE.findall(html_text):
        if token.startswith("<"):
            tag_match = _TAG_NAME_RE.match(token)
            if tag_match:
                tag_name = tag_match.group(1).lower()
                if tag_name in open_counts:
                    is_closing = token.startswith("</")
                    is_self_closing = token.rstrip().endswith("/>")
                    if is_closing:
                        open_counts[tag_name] = max(0, open_counts[tag_name] - 1)
                    elif not is_self_closing:
                        open_counts[tag_name] += 1
            chunks.append(token)
            continue

        if any(count > 0 for count in open_counts.values()):
            chunks.append(token)
        else:
            chunks.append(_linkify_plain_text_segment(token))

    return "".join(chunks)


def _render_glfm_alerts(html_text: str) -> str:
    """Convert GLFM alert blockquotes to semantic alert HTML."""
    if not isinstance(html_text, str):
        return html_text

    def _repl(match: re.Match[str]) -> str:
        inner = match.group(1)
        first_paragraph = _FIRST_PARAGRAPH_RE.match(inner)
        if not first_paragraph:
            return match.group(0)

        first_paragraph_html = first_paragraph.group(1)
        first_line_html, _, body_from_first_paragraph = first_paragraph_html.partition(
            "\n"
        )
        first_line_text = html.unescape(_strip_tags(first_line_html)).strip()
        marker = _ALERT_MARKER_RE.match(first_line_text)
        if not marker:
            return match.group(0)

        alert_type = marker.group(1).lower()
        custom_title = (marker.group(2) or "").strip()
        title = html.escape(custom_title or _ALERT_DEFAULT_TITLES[alert_type])

        body_from_first_paragraph = re.sub(
            r"^(<br\s*/?>\s*)+",
            "",
            body_from_first_paragraph.lstrip(),
            flags=re.IGNORECASE,
        )
        rest = inner[first_paragraph.end() :].strip()
        body_parts: list[str] = []
        if body_from_first_paragraph.strip():
            body_parts.append(f"<p>{body_from_first_paragraph}</p>")
        if rest:
            body_parts.append(rest)
        joined_body = "\n".join(body_parts)
        body = f"\n{joined_body}\n" if joined_body else "\n"

        return (
            f'<blockquote class="glfm-alert glfm-alert-{alert_type}">\n'
            f'<p class="glfm-alert-title">{title}</p>{body}</blockquote>'
        )

    return _BLOCKQUOTE_RE.sub(_repl, html_text)


def _render_glfm_toc(html_text: str) -> str:
    """Replace GLFM [[_TOC_]] marker paragraphs with a generated TOC nav."""
    if not isinstance(html_text, str):
        return html_text

    headings: list[tuple[int, str, str]] = []
    for match in _HEADING_WITH_ID_RE.finditer(html_text):
        level = int(match.group(1))
        heading_id = match.group(2)
        heading_text = html.unescape(_strip_tags(match.group(3))).strip()
        if not heading_text:
            continue
        headings.append((level, heading_id, heading_text))

    if not headings:
        return _GLFM_TOC_MARKER_RE.sub("", html_text)

    items = "\n".join(
        (
            f'<li class="toc-level-{level}"><a href="#{html.escape(heading_id, quote=True)}">'
            f"{html.escape(heading_text)}</a></li>"
        )
        for level, heading_id, heading_text in headings
    )
    toc_html = f'<nav class="table-of-contents glfm-toc">\n<ul>\n{items}\n</ul>\n</nav>'
    return _GLFM_TOC_MARKER_RE.sub(toc_html, html_text)


def _render_glfm_color_chips(html_text: str) -> str:
    """Render GLFM inline color literals in <code> as visual color chips."""
    if not isinstance(html_text, str):
        return html_text

    chunks: list[str] = []
    pre_depth = 0
    pending_code_open_tag: str | None = None
    pending_code_tokens: list[str] = []

    for token in _TEXT_OR_TAG_RE.findall(html_text):
        if pending_code_open_tag is not None:
            if token.startswith("</code"):
                raw_literal = html.unescape("".join(pending_code_tokens))
                if _GLFM_COLOR_HEX_RE.fullmatch(
                    raw_literal
                ) or _GLFM_COLOR_FUNCTION_RE.fullmatch(raw_literal):
                    safe_literal = html.escape(raw_literal)
                    safe_color = html.escape(raw_literal.lower(), quote=True)
                    safe_label = html.escape(f"Color swatch {raw_literal}", quote=True)
                    chunks.append(
                        '<span class="glfm-color-chip" role="img" '
                        f'aria-label="{safe_label}">'
                        '<span class="glfm-color-chip-swatch" '
                        f'style="background-color: {safe_color};"></span>'
                        f"<code>{safe_literal}</code>"
                        "</span>"
                    )
                else:
                    chunks.append(pending_code_open_tag)
                    chunks.extend(pending_code_tokens)
                    chunks.append(token)

                pending_code_open_tag = None
                pending_code_tokens = []
            else:
                pending_code_tokens.append(token)
            continue

        if token.startswith("<"):
            tag_match = _TAG_NAME_RE.match(token)
            if tag_match:
                tag_name = tag_match.group(1).lower()
                is_closing = token.startswith("</")
                is_self_closing = token.rstrip().endswith("/>")
                if tag_name == "pre":
                    if is_closing:
                        pre_depth = max(0, pre_depth - 1)
                    elif not is_self_closing:
                        pre_depth += 1
                elif (
                    tag_name == "code"
                    and pre_depth == 0
                    and not is_closing
                    and not is_self_closing
                ):
                    pending_code_open_tag = token
                    pending_code_tokens = []
                    continue

            chunks.append(token)
            continue

        chunks.append(token)

    if pending_code_open_tag is not None:
        chunks.append(pending_code_open_tag)
        chunks.extend(pending_code_tokens)

    return "".join(chunks)


def _render_glfm_emoji_shortcodes(html_text: str) -> str:
    """Replace known GLFM emoji shortcodes with Unicode emoji."""
    if not isinstance(html_text, str):
        return html_text

    open_counts = {tag: 0 for tag in _EMOJI_EXCLUDED_TAGS}
    chunks: list[str] = []

    def _replace_shortcodes(text: str) -> str:
        def _repl(match: re.Match[str]) -> str:
            shortcode = match.group(1).lower()
            return _GLFM_EMOJI_SHORTCODES.get(shortcode, match.group(0))

        return _EMOJI_SHORTCODE_RE.sub(_repl, text)

    for token in _TEXT_OR_TAG_RE.findall(html_text):
        if token.startswith("<"):
            tag_match = _TAG_NAME_RE.match(token)
            if tag_match:
                tag_name = tag_match.group(1).lower()
                if tag_name in open_counts:
                    is_closing = token.startswith("</")
                    is_self_closing = token.rstrip().endswith("/>")
                    if is_closing:
                        open_counts[tag_name] = max(0, open_counts[tag_name] - 1)
                    elif not is_self_closing:
                        open_counts[tag_name] += 1
            chunks.append(token)
            continue

        if any(count > 0 for count in open_counts.values()):
            chunks.append(token)
        else:
            chunks.append(_replace_shortcodes(token))

    return "".join(chunks)


def _separate_adjacent_footnote_superscripts(html_text: str) -> str:
    """Insert superscript commas between adjacent footnote references."""
    if not isinstance(html_text, str):
        return html_text
    return _ADJACENT_FOOTNOTE_SUP_RE.sub(r"\1,\2", html_text)


def _place_footnote_superscripts_after_punctuation(html_text: str) -> str:
    """Move trailing punctuation ahead of adjacent footnote superscripts."""
    if not isinstance(html_text, str):
        return html_text
    chunks: list[str] = []
    cursor = 0
    text_length = len(html_text)

    while cursor < text_length:
        start = html_text.find(_FOOTNOTE_SUP_OPEN, cursor)
        if start == -1:
            chunks.append(html_text[cursor:])
            break

        chunks.append(html_text[cursor:start])
        run_cursor = start
        run_parts: list[str] = []

        while html_text.startswith(_FOOTNOTE_SUP_OPEN, run_cursor):
            close_index = html_text.find(_FOOTNOTE_SUP_CLOSE, run_cursor)
            if close_index == -1:
                chunks.append(html_text[start:])
                return "".join(chunks)

            close_end = close_index + len(_FOOTNOTE_SUP_CLOSE)
            run_parts.append(html_text[run_cursor:close_end])
            run_cursor = close_end

        if (
            run_cursor < text_length
            and html_text[run_cursor] in _PUNCTUATION_AFTER_FOOTNOTES
        ):
            chunks.append(html_text[run_cursor])
            chunks.append("".join(run_parts))
            cursor = run_cursor + 1
            continue

        chunks.append("".join(run_parts))
        cursor = run_cursor

    return "".join(chunks)


def _postprocess_rendered_html(html_text: str) -> str:
    return _place_footnote_superscripts_after_punctuation(
        _separate_adjacent_footnote_superscripts(
            _render_glfm_emoji_shortcodes(
                _render_glfm_color_chips(
                    _render_glfm_toc(
                        _add_heading_ids(
                            _render_glfm_alerts(_linkify_extended_autolinks(html_text))
                        )
                    )
                )
            )
        )
    )


class AbstractMarkdownRenderer(ABC):
    """Defines the Markdown-to-HTML rendering interface."""

    @abstractmethod
    def render(self, text: str) -> str:
        """Render Markdown text to HTML."""

    @abstractmethod
    def get_version(self) -> str:
        """Return the underlying renderer version."""


class MistuneRenderer(AbstractMarkdownRenderer):
    """Render Markdown to HTML with Mermaid fence support."""

    MERMAID_VERSION = MERMAID_VERSION

    def __init__(self) -> None:
        # TODO: Enable additional mistune 3 plugins for full ExtraMark support.
        # The following plugins ship with mistune 3 and only need to be added
        # to the list below — no extra dependencies required:
        #   "task_lists"  – GFM task-list checkboxes  (- [x] / - [ ])
        #   "def_list"    – ExtraMark definition lists (Term\n:   Definition)
        #   "abbr"        – ExtraMark abbreviations   (*[HTML]: expansion)
        # See: tests/test_extramark_compat.py and tests/test_gfm_compat.py
        # "superscript" and "subscript" are already enabled (x^2^, H~2~O,
        # and scientific notation such as M~🜨~ for Earth mass).
        # "footnotes" is enabled for [^label] reference/definition support.
        self._renderer = mistune.create_markdown(
            renderer=mistune.HTMLRenderer(escape=False),
            plugins=[
                "strikethrough",
                "table",
                "url",
                "subscript",
                "superscript",
                "footnotes",
            ],
        )

    def render_preprocessed(self, text: str) -> str:
        """Run mistune on *text* without any Mermaid preprocessing."""
        return _postprocess_rendered_html(self._renderer(text))

    def render(self, text: str) -> str:
        from calamus.mermaid_support import (
            SubprocessMermaidRenderer,
            preprocess_markdown_for_static_export,
        )

        if SubprocessMermaidRenderer().is_available():
            text = preprocess_markdown_for_static_export(text)
            return _postprocess_rendered_html(self._renderer(text))

        prepared = self._prepare_mermaid_blocks(text)
        return _postprocess_rendered_html(self._renderer(prepared))

    def get_version(self) -> str:
        return getattr(mistune, "__version__", "unknown")

    def _prepare_mermaid_blocks(self, text: str) -> str:
        pattern = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)

        def repl(match: re.Match[str]) -> str:
            diagram_source = html.escape(match.group(1).strip())
            return f'\n<pre class="mermaid">{diagram_source}</pre>\n'

        return pattern.sub(repl, text)

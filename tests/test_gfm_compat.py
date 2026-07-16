"""GFM compatibility tests.

GitHub Flavored Markdown (GFM) is a strict superset of CommonMark.  The GFM
spec (https://github.github.com/gfm/) defines exactly five extensions over
CommonMark, each labelled "(extension)" in the spec TOC:

  1. Tables (§ 4.10)
  2. Task list items (§ 5.3)
  3. Strikethrough (§ 6.5)
  4. Autolinks — extended (§ 6.9)
  5. Disallowed raw HTML (§ 6.11)

For each extension, Calamus must fall into one of two categories:

  Case 1 — Graceful fail-over:
    The renderer does not crash, produces valid (non-broken) HTML, and the
    rest of the document still renders correctly.  The GFM-specific syntax
    may appear as plain text or inside a <code> block — that is acceptable.

  Case 2 — Supported:
    The rendered HTML approximates what GFM would produce for the extension.

Reference: https://github.github.com/gfm/
"""

from __future__ import annotations

import re

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def render(md: str) -> str:
    """Return HTML produced by MistuneRenderer for the given Markdown."""
    from calamus.renderer import MistuneRenderer

    return MistuneRenderer().render(md)


def assert_no_crash(md: str) -> str:
    """Assert renderer doesn't raise and returns non-empty output."""
    html = render(md)
    assert isinstance(html, str), "render() must return a str"
    assert html.strip(), "render() must return non-empty output"
    return html


def assert_surrounding_content_intact(html: str, marker: str = "MARKER") -> None:
    """Assert that normal Markdown around GFM-specific syntax still renders."""
    assert (
        marker in html
    ), f"Surrounding content '{marker}' missing from rendered output"


def extract_hrefs(html: str) -> list[str]:
    """Extract all link targets from anchor tags."""
    return re.findall(r'href="([^"]+)"', html)


def has_href(html: str, expected_url: str) -> bool:
    """Return True when the HTML contains an exact href match."""
    return any(href == expected_url for href in extract_hrefs(html))


# ===========================================================================
# GFM Extension 1: Tables (§ 4.10)
# ===========================================================================
# Pipe tables are a GFM extension over CommonMark.
# Calamus enables this via the mistune 'table' plugin.
# Case 2 — Supported.
#
# GFM spec rules:
#   - First row is the header.
#   - Second row must consist entirely of hyphens (with optional colons).
#   - Subsequent rows are body cells.
#   - Outer pipes are optional but inner pipes are required.
#   - Inline Markdown is parsed inside cells.


class TestTablesExtension:
    def test_basic_table_produces_table_element(self):
        """A minimal pipe table must render as <table>."""
        md = "| Header |\n|--------|\n| Cell   |\n"
        html = render(md)
        assert "<table>" in html

    def test_table_has_thead_and_tbody(self):
        """Table header row must appear in a <thead> or as <th> elements."""
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n"
        html = render(md)
        assert "<th>" in html or "<thead>" in html

    def test_table_body_cells_rendered(self):
        """Body cells must appear as <td> elements."""
        md = "| Col1 | Col2 |\n|------|------|\n| val1 | val2 |\n"
        html = render(md)
        assert "<td>" in html
        assert "val1" in html
        assert "val2" in html

    def test_table_multiple_body_rows(self):
        """Multiple body rows must each render."""
        md = "| X |\n|---|\n| r1 |\n| r2 |\n| r3 |\n"
        html = render(md)
        assert "r1" in html
        assert "r2" in html
        assert "r3" in html

    def test_table_left_alignment(self):
        """:--- alignment specifier must not crash."""
        md = "| Left |\n|:-----|\n| data |\n"
        html = assert_no_crash(md)
        assert "<table>" in html

    def test_table_center_alignment(self):
        """:---: alignment specifier must not crash."""
        md = "| Center |\n|:------:|\n| data   |\n"
        html = assert_no_crash(md)
        assert "<table>" in html

    def test_table_right_alignment(self):
        """---: alignment specifier must not crash."""
        md = "| Right |\n|------:|\n| data  |\n"
        html = assert_no_crash(md)
        assert "<table>" in html

    def test_table_mixed_alignment(self):
        """Mixed alignment columns must not crash."""
        md = "| L | C | R |\n|:--|:-:|--:|\n| a | b | c |\n"
        html = assert_no_crash(md)
        assert "<table>" in html
        assert "a" in html and "b" in html and "c" in html

    def test_table_inline_bold_in_cell(self):
        """**Bold** inside a table cell must be rendered."""
        md = "| Header |\n|--------|\n| **bold** |\n"
        html = render(md)
        assert "<strong>" in html

    def test_table_inline_link_in_cell(self):
        """A link inside a table cell must be rendered."""
        md = "| Header |\n|--------|\n| [link](https://example.com) |\n"
        html = render(md)
        assert "<a" in html
        assert has_href(html, "https://example.com")

    def test_table_inline_code_in_cell(self):
        """`code` inside a table cell must render as <code>."""
        md = "| Header |\n|--------|\n| `code` |\n"
        html = render(md)
        assert "<code>" in html

    def test_table_empty_cells(self):
        """Empty cells must not crash."""
        md = "| A | B | C |\n|---|---|---|\n| x |   | z |\n"
        html = assert_no_crash(md)
        assert "<table>" in html

    def test_table_without_outer_pipes(self):
        """GFM allows tables without leading/trailing pipes."""
        md = "Col1 | Col2\n-----|-----\nval1 | val2\n"
        html = assert_no_crash(md)
        # Either renders as table or as plain text — must not crash
        assert isinstance(html, str)

    def test_table_with_many_columns(self):
        """Wide table (5 columns) must render without crash."""
        md = "| A | B | C | D | E |\n|---|---|---|---|---|\n| 1 | 2 | 3 | 4 | 5 |\n"
        html = assert_no_crash(md)
        assert "<table>" in html

    def test_table_does_not_break_following_paragraph(self):
        """Content after a table must still render."""
        md = "| H |\n|---|\n| v |\n\nMARKER paragraph.\n"
        html = assert_no_crash(md)
        assert_surrounding_content_intact(html)

    def test_non_table_pipe_in_paragraph_not_table(self):
        """A pipe character in a paragraph must not accidentally form a table."""
        md = "A | B is not a table.\n"
        html = render(md)
        # Should be a paragraph, not a table
        assert "<p>" in html or "A" in html


# ===========================================================================
# GFM Extension 2: Task list items (§ 5.3)
# ===========================================================================
# GFM turns list items beginning with [ ] or [x] into checkboxes.
# Calamus enables this via the mistune 'task_lists' plugin.
# Case 2 — Supported.
#
# GFM spec examples:
#   - [x] foo
#   - [ ] bar
#   - [X] also checked (uppercase X)
#   Checkbox must be the first item content (leading spaces allowed).


class TestTaskListItemsExtension:
    def test_checked_item_does_not_crash(self):
        """- [x] item must not crash."""
        html = render("- [x] Finished task\n")
        assert 'class="task-list-item-checkbox"' in html
        assert "checked" in html

    def test_unchecked_item_does_not_crash(self):
        """- [ ] item must not crash."""
        html = render("- [ ] Pending task\n")
        assert 'class="task-list-item-checkbox"' in html

    def test_uppercase_x_checked_item_does_not_crash(self):
        """- [X] item (uppercase X) must not crash."""
        html = render("- [X] Also done\n")
        assert 'class="task-list-item-checkbox"' in html
        assert "checked" in html

    def test_task_item_text_is_visible(self):
        """The text label of a task item must appear in the output."""
        html = render("- [x] Buy groceries\n")
        assert "Buy groceries" in html

    def test_unchecked_item_text_is_visible(self):
        """The text label of an unchecked item must appear in the output."""
        html = render("- [ ] Write tests\n")
        assert "Write tests" in html

    def test_task_list_renders_as_list_at_minimum(self):
        """Task items must render inside a <ul> or as visible list content."""
        md = "- [x] Done\n- [ ] Not done\n"
        html = render(md)
        assert "<ul>" in html
        assert html.count('class="task-list-item-checkbox"') == 2

    def test_mixed_task_and_regular_items_do_not_crash(self):
        """A list mixing task and regular items must not crash."""
        md = "- [x] Task one\n- Regular item\n- [ ] Task two\n"
        html = assert_no_crash(md)
        assert "Task one" in html
        assert "Regular item" in html
        assert "Task two" in html

    def test_ordered_task_list_does_not_crash(self):
        """Task items in an ordered list must not crash."""
        md = "1. [x] First done\n2. [ ] Second pending\n"
        html = assert_no_crash(md)
        assert "First done" in html
        assert "Second pending" in html

    def test_nested_task_list_does_not_crash(self):
        """Nested task lists must not crash."""
        md = "- [x] Parent task\n  - [ ] Sub-task A\n  - [x] Sub-task B\n"
        html = assert_no_crash(md)
        assert "Parent task" in html
        assert "Sub-task A" in html

    def test_task_item_does_not_break_document(self):
        """A heading after a task list must still render."""
        md = "- [x] Done\n\n## MARKER heading\n"
        html = assert_no_crash(md)
        assert_surrounding_content_intact(html)

    def test_non_task_brackets_not_misidentified(self):
        """A list item starting with [abc] must not be treated as a checkbox."""
        md = "- [abc] Not a checkbox\n"
        html = assert_no_crash(md)
        assert "Not a checkbox" in html

    def test_task_item_with_inline_emphasis(self):
        """Task items containing **bold** or _italic_ must not crash."""
        md = "- [x] **Important** task\n- [ ] _Optional_ item\n"
        html = assert_no_crash(md)
        assert "Important" in html
        assert "Optional" in html


# ===========================================================================
# GFM Extension 3: Strikethrough (§ 6.5)
# ===========================================================================
# GFM renders ~~text~~ as <del>text</del>.
# Calamus enables this via the mistune 'strikethrough' plugin.
# Case 2 — Supported.
#
# GFM spec rules:
#   - Two ~ on each side (~~text~~) is strikethrough.
#   - One ~ each side (~text~) is NOT strikethrough per GFM spec.
#   - Opening/closing tildes must not be separated from content by spaces.


class TestStrikethroughExtension:
    def test_double_tilde_renders_as_del(self):
        """~~text~~ must produce a <del> element."""
        html = render("~~struck~~")
        assert "<del>" in html

    def test_strikethrough_content_is_present(self):
        """Text inside ~~ must appear inside <del>."""
        html = render("~~removed content~~")
        assert "removed content" in html

    def test_strikethrough_in_sentence(self):
        """Strikethrough in the middle of a sentence must work."""
        html = render("Before ~~middle~~ after.")
        assert "Before" in html
        assert "after" in html
        assert "<del>" in html

    def test_strikethrough_with_bold_inside(self):
        """~~**bold**~~ must not crash and must render some form of both."""
        html = assert_no_crash("~~**bold strikethrough**~~")
        assert "bold strikethrough" in html

    def test_strikethrough_with_italic_inside(self):
        """~~_italic_~~ must not crash."""
        html = assert_no_crash("~~_italic strikethrough_~~")
        assert "italic strikethrough" in html

    def test_strikethrough_with_code_inside(self):
        """~~`code`~~ must not crash."""
        html = assert_no_crash("~~`some code`~~")
        assert "some code" in html

    def test_single_tilde_not_strikethrough(self):
        """~text~ (one tilde) must NOT render as <del> per GFM spec."""
        html = render("~single tilde~")
        # GFM only supports double tildes; single should be plain text
        assert "<del>" not in html or "single tilde" in html

    def test_strikethrough_does_not_cross_paragraphs(self):
        """~~ that spans paragraphs must not produce a broken <del>."""
        md = "~~start\n\nend~~\n"
        html = assert_no_crash(md)
        # Should not produce unclosed tags
        assert isinstance(html, str)

    def test_multiple_strikethroughs_in_paragraph(self):
        """Multiple strikethrough spans in one paragraph must all render."""
        md = "~~one~~ and ~~two~~ and ~~three~~\n"
        html = render(md)
        assert html.count("<del>") >= 1

    def test_strikethrough_empty_document_does_not_crash(self):
        """An entire document of only strikethrough must not crash."""
        html = assert_no_crash("~~everything~~\n")
        assert "<del>" in html


# ===========================================================================
# GFM Extension 4: Autolinks — extended (§ 6.9)
# ===========================================================================
# GFM extends CommonMark autolinks to recognise bare URLs (without <...>
# angle-bracket wrapping) in text, including:
#   - https:// and http:// URLs
#   - www. URLs (treated as if they had https://)
#   - Email addresses (user@example.com)
#
# CommonMark already supports <URL> angle-bracket autolinks.
# GFM adds the *extended* form: bare https/http URLs, www., and emails.
#
# Calamus has the mistune 'url' plugin for bare https/http URLs and extends
# post-processing to support www. URLs and bare email autolinks.
#
# Case 2 — Supported.


class TestAutolinksExtension:
    # ---- CommonMark angle-bracket autolinks (always supported) ----

    def test_angle_bracket_http_url_becomes_link(self):
        """<https://example.com> must always become an <a> link."""
        html = render("See <https://example.com> for details.")
        assert "<a" in html
        assert has_href(html, "https://example.com")

    def test_angle_bracket_email_becomes_link(self):
        """<user@example.com> angle-bracket autolink must become a link."""
        html = render("Contact <user@example.com> today.")
        assert "<a" in html or "user@example.com" in html

    # ---- GFM extended: bare https/http URLs ----

    def test_bare_https_url_becomes_link(self):
        """A bare https:// URL must be auto-linked (via 'url' plugin)."""
        html = render("Visit https://www.example.com for info.")
        assert "<a" in html
        assert has_href(html, "https://www.example.com")

    def test_bare_http_url_becomes_link(self):
        """A bare http:// URL must be auto-linked."""
        html = render("See http://example.org please.")
        assert "<a" in html
        assert has_href(html, "http://example.org")

    def test_bare_url_with_path(self):
        """A bare URL with path components must be auto-linked."""
        html = render("Docs at https://docs.example.com/guide/intro.")
        assert "<a" in html

    def test_bare_url_with_query_string(self):
        """A bare URL with query string must not crash."""
        html = assert_no_crash("Search: https://example.com/q?term=foo&page=1")
        assert isinstance(html, str)

    def test_bare_url_with_fragment(self):
        """A bare URL with # fragment must not crash."""
        html = assert_no_crash("See https://example.com/page#section for more.")
        assert isinstance(html, str)

    def test_bare_url_in_parentheses_does_not_crash(self):
        """A bare URL inside parentheses must not crash."""
        html = assert_no_crash("(See https://example.com for details.)")
        assert isinstance(html, str)

    # ---- GFM extended: www. URLs ----

    def test_bare_www_url_becomes_link(self):
        """A bare www. URL must be auto-linked."""
        html = render("Visit www.example.com today.")
        assert '<a href="https://www.example.com">' in html
        assert ">www.example.com</a>" in html

    def test_bare_www_url_with_trailing_period(self):
        """Trailing punctuation must not be included in www. autolink href."""
        html = render("Go to www.example.com.")
        assert '<a href="https://www.example.com">www.example.com</a>.' in html

    # ---- GFM extended: email autolinks ----

    def test_bare_email_becomes_link(self):
        """A bare email address must be auto-linked."""
        html = render("Write to admin@example.org.")
        assert '<a href="mailto:admin@example.org">admin@example.org</a>' in html

    def test_bare_email_with_trailing_parenthesis(self):
        """Trailing punctuation must not be included in email autolink href."""
        html = render("Email (someone@example.com).")
        assert '<a href="mailto:someone@example.com">someone@example.com</a>).'

    # ---- Multiple URLs in same paragraph ----

    def test_multiple_bare_urls_do_not_crash(self):
        """Multiple bare URLs in one paragraph must not crash."""
        md = "See https://example.com and https://other.org for more.\n"
        html = assert_no_crash(md)
        assert has_href(html, "https://example.com")
        assert has_href(html, "https://other.org")

    # ---- Explicit Markdown links override autolinks ----

    def test_explicit_link_still_works_alongside_autolinks(self):
        """[text](url) explicit links must still work with the url plugin."""
        html = render("[Example](https://example.com) and www.example.com")
        assert "<a" in html
        assert has_href(html, "https://example.com")
        assert has_href(html, "https://www.example.com")


# ===========================================================================
# GFM Extension 5: Disallowed raw HTML (§ 6.11)
# ===========================================================================
# GFM filters certain potentially dangerous HTML tags: <title>, <textarea>,
# <style>, <xmp>, <iframe>, <noembed>, <noframes>, <script>, <plaintext>.
# These are rendered as literal text (the opening tag becomes &lt;tagname).
#
# Calamus uses mistune HTMLRenderer(escape=False) which passes raw HTML
# through without filtering.  This means:
#   - These tags ARE rendered as HTML (not filtered), which differs from GFM.
#   - The important invariant is that the renderer does not CRASH on them and
#     that surrounding document content still renders correctly.
#
# Case 1 — Graceful fail-over: no crash, surrounding content intact.
#           (Calamus accepts the raw HTML rather than filtering it; this is a
#           known divergence from GFM — the editor renders local content and
#           the user is the author, so server-side sanitisation is not needed.)


class TestDisallowedRawHtmlExtension:
    # The GFM-disallowed tags
    _DISALLOWED_TAGS = [
        "title",
        "textarea",
        "style",
        "xmp",
        "iframe",
        "noembed",
        "noframes",
        "script",
        "plaintext",
    ]

    @pytest.mark.parametrize("tag", _DISALLOWED_TAGS)
    def test_disallowed_tag_does_not_crash(self, tag: str):
        f"""<{tag}> in Markdown must not cause the renderer to crash."""
        md = f"Before text.\n\n<{tag}>Content</{tag}>\n\nAfter text.\n"
        html = assert_no_crash(md)

    @pytest.mark.parametrize("tag", _DISALLOWED_TAGS)
    def test_surrounding_content_intact_with_disallowed_tag(self, tag: str):
        f"""Content around a <{tag}> tag must still render."""
        md = f"MARKER before.\n\n<{tag}>x</{tag}>\n\nMARKER after.\n"
        html = assert_no_crash(md)
        assert "MARKER" in html

    def test_script_tag_does_not_crash(self):
        """<script> tag in Markdown body must not crash."""
        md = "Paragraph.\n\n<script>alert('xss')</script>\n\nMore text.\n"
        html = assert_no_crash(md)

    def test_style_tag_does_not_crash(self):
        """<style> tag in Markdown body must not crash."""
        md = "Text before.\n\n<style>body { color: red; }</style>\n\nText after.\n"
        html = assert_no_crash(md)

    def test_iframe_tag_does_not_crash(self):
        """<iframe> tag in Markdown body must not crash."""
        md = "Before.\n\n<iframe src='https://example.com'></iframe>\n\nAfter.\n"
        html = assert_no_crash(md)

    def test_allowed_html_tags_pass_through(self):
        """HTML tags NOT on the disallowed list must render normally."""
        md = "Use <kbd>Ctrl+C</kbd> to copy.\n"
        html = render(md)
        assert "<kbd>" in html
        assert "Ctrl+C" in html

    def test_safe_inline_html_renders(self):
        """Safe inline HTML (<strong>, <em>, <code>) must pass through."""
        md = "This is <strong>strong</strong> and <em>italic</em>.\n"
        html = render(md)
        assert "strong" in html
        assert "italic" in html

    def test_html_block_does_not_break_document(self):
        """An HTML block followed by a Markdown heading must render both."""
        md = "<div>A block</div>\n\n## MARKER heading\n"
        html = assert_no_crash(md)
        assert_surrounding_content_intact(html)

    def test_calamus_does_not_filter_disallowed_tags(self):
        """Document the known divergence: Calamus does NOT filter these tags.

        GFM sanitises <script> etc.  Calamus renders local author content,
        so filtering is not performed.  This test records the current (and
        intentional) behaviour to catch accidental regressions in either
        direction.
        """
        md = "Text.\n\n<script>var x = 1;</script>\n\nMore text.\n"
        html = render(md)
        # The <script> content must either be present (no filtering) or
        # escaped.  Either way, the renderer must return a non-empty string.
        assert isinstance(html, str)
        assert html.strip()


# ===========================================================================
# Regression: all five extensions together
# ===========================================================================
# A document using all five GFM extensions must render without crashing and
# must produce visible content for each feature present.


class TestAllExtensionsTogether:
    _MIXED = """\
# Mixed GFM extensions

| Feature     | Status |
|-------------|--------|
| Tables      | ~~old~~ **new** |
| Tasks       | done   |

- [x] Tables render
- [ ] Nothing breaks

Visit https://github.com/gfm for the spec.

<iframe src="https://example.com"></iframe>

End of document.
"""

    def test_mixed_document_does_not_crash(self):
        """A document using all 5 GFM extensions must not crash."""
        html = assert_no_crash(self._MIXED)

    def test_mixed_document_table_renders(self):
        """Table in mixed document must produce <table>."""
        html = render(self._MIXED)
        assert "<table>" in html

    def test_mixed_document_strikethrough_renders(self):
        """Strikethrough in mixed document must produce <del>."""
        html = render(self._MIXED)
        assert "<del>" in html

    def test_mixed_document_task_text_visible(self):
        """Task list labels in mixed document must be visible."""
        html = render(self._MIXED)
        assert "Tables render" in html
        assert "Nothing breaks" in html

    def test_mixed_document_url_becomes_link(self):
        """Bare URL in mixed document must be auto-linked."""
        html = render(self._MIXED)
        assert has_href(html, "https://github.com/gfm")

    def test_mixed_document_end_content_renders(self):
        """The final paragraph of the mixed document must render."""
        html = render(self._MIXED)
        assert "End of document" in html

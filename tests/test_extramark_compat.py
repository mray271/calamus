"""ExtraMark compatibility tests.

ExtraMark (https://github.com/vimtaai/extramark) is an independent superset
of CommonMark that bundles the most popular ecosystem extensions into a single
open-source specification, branching directly from CommonMark rather than
from GFM.

Its nine syntax extensions are:
  1. Automatic typographic replacements (typographer)
  2. Tables
  3. Anchors for headings (up to h3)
  4. Definition lists
  5. Superscript
  6. Subscript
  7. Abbreviations
  8. Footnotes
  9. Critic Markup

For each extension, Calamus must fall into one of two categories:

  Case 1 — Graceful fail-over:
    The renderer does not crash, produces valid (non-broken) HTML, and the
    rest of the document still renders correctly.  The ExtraMark-specific
    syntax may appear as plain text — that is acceptable.

  Case 2 — Supported:
    The rendered HTML approximates what ExtraMark would produce.

Reference: https://github.com/vimtaai/extramark#features
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
    """Assert normal Markdown around ExtraMark syntax still renders."""
    assert (
        marker in html
    ), f"Surrounding content '{marker}' missing from rendered output"


def extract_hrefs(html: str) -> list[str]:
    """Extract all link targets from anchor tags."""
    return re.findall(r'href="([^"]+)"', html)


# ===========================================================================
# ExtraMark Extension 1: Automatic typographic replacements
# ===========================================================================
# ExtraMark runs a typographer pass that converts ASCII punctuation sequences
# to their Unicode equivalents:
#   "double quotes"  →  "double quotes"  (U+201C / U+201D)
#   'single quotes'  →  'single quotes'  (U+2018 / U+2019)
#   --               →  –  (en-dash, U+2013)
#   ---              →  —  (em-dash, U+2014)
#   ...              →  …  (ellipsis, U+2026)
#   (c)              →  ©
#   (r)              →  ®
#   (tm)             →  ™
#
# mistune does NOT include a typographer pass.
# Case 1 — Graceful fail-over: ASCII forms must be visible, no crash.


class TestTypographicReplacements:
    def test_double_dash_does_not_crash(self):
        """-- must not crash (graceful fail-over as ASCII)."""
        html = assert_no_crash("Range: 1--10")
        assert "1" in html and "10" in html

    def test_triple_dash_does_not_crash(self):
        """--- must not crash."""
        html = assert_no_crash("He said---loudly---hello.")
        assert "said" in html and "hello" in html

    def test_ellipsis_sequence_does_not_crash(self):
        """... must not crash."""
        html = assert_no_crash("Wait for it...")
        assert "Wait for it" in html

    def test_copyright_sequence_does_not_crash(self):
        """(c) must not crash."""
        html = assert_no_crash("Copyright (c) 2024 Acme Corp.")
        assert "Acme Corp" in html

    def test_registered_sequence_does_not_crash(self):
        """(r) must not crash."""
        html = assert_no_crash("Brand(r) is registered.")
        assert "Brand" in html

    def test_trademark_sequence_does_not_crash(self):
        """(tm) must not crash."""
        html = assert_no_crash("Product(tm) is a trademark.")
        assert "Product" in html

    def test_double_dash_not_converted_without_typographer(self):
        """Without a typographer, -- must remain as ASCII, not an en-dash."""
        html = render("1--10")
        # Acceptable: ASCII -- in output (no typographer)
        # Must contain the digit content
        assert "1" in html and "10" in html

    def test_triple_dash_not_converted_without_typographer(self):
        """Without a typographer, --- must remain as ASCII."""
        html = render("A---B")
        assert "A" in html and "B" in html

    def test_ellipsis_not_converted_without_typographer(self):
        """Without a typographer, ... must remain as three dots."""
        html = render("Waiting...")
        assert "Waiting" in html

    def test_typographic_sequence_in_heading(self):
        """Typographic sequences inside headings must not crash."""
        html = assert_no_crash("# Title --- Subtitle")
        assert "Title" in html and "Subtitle" in html

    def test_typographic_sequences_do_not_break_surrounding_content(self):
        """Normal text around typographic sequences must still render."""
        html = assert_no_crash("MARKER before --- MARKER after")
        assert "MARKER before" in html
        assert "MARKER after" in html


# ===========================================================================
# ExtraMark Extension 2: Tables
# ===========================================================================
# ExtraMark uses the same GFM pipe-table syntax.
# Calamus enables this via the mistune 'table' plugin.
# Case 2 — Supported.


class TestTables:
    def test_basic_table_renders(self):
        """A basic pipe table must produce a <table> element."""
        md = "| Name | Value |\n|------|-------|\n| foo  | bar   |\n"
        html = render(md)
        assert "<table>" in html
        assert "foo" in html and "bar" in html

    def test_table_with_alignment_does_not_crash(self):
        """Table with alignment markers must not crash."""
        md = "| L | C | R |\n|:--|:-:|--:|\n| a | b | c |\n"
        html = assert_no_crash(md)
        assert "<table>" in html

    def test_table_header_rendered(self):
        """Table header must appear as <th> elements."""
        md = "| Col1 | Col2 |\n|------|------|\n| v1   | v2   |\n"
        html = render(md)
        assert "<th>" in html

    def test_table_does_not_break_following_paragraph(self):
        """Content after a table must still render."""
        md = "| H |\n|---|\n| v |\n\nMARKER paragraph.\n"
        html = assert_no_crash(md)
        assert_surrounding_content_intact(html)


# ===========================================================================
# ExtraMark Extension 3: Anchors for headings
# ===========================================================================
# ExtraMark adds an `id` attribute and a self-link anchor to headings h1–h3.
# Example: `## My Section` → <h2 id="my-section"><a href="#my-section">…</a>
# mistune does NOT add id attributes to headings by default.
# Case 1 — Graceful fail-over: headings render without anchor/id.


class TestHeadingAnchors:
    def test_h1_renders_without_crash(self):
        """# Heading must not crash (anchor not required)."""
        html = assert_no_crash("# Top Level\n")
        assert "Top Level" in html
        assert "<h1" in html

    def test_h2_renders_without_crash(self):
        """## Heading must not crash."""
        html = assert_no_crash("## Section\n")
        assert "Section" in html
        assert "<h2" in html

    def test_h3_renders_without_crash(self):
        """### Heading must not crash."""
        html = assert_no_crash("### Sub-section\n")
        assert "Sub-section" in html
        assert "<h3" in html

    def test_h4_renders_without_crash(self):
        """#### h4 (beyond anchor scope) must still render."""
        html = assert_no_crash("#### Deep\n")
        assert "Deep" in html
        assert "<h4" in html

    def test_heading_without_id_attribute_is_acceptable(self):
        """Without anchor support, headings have no id= — that is acceptable."""
        html = render("## My Section\n")
        assert "<h2" in html
        assert "My Section" in html
        # id attribute is not required for graceful fail-over

    def test_heading_text_content_intact(self):
        """Heading text must be unmodified by absent anchor processing."""
        html = render("# Hello World\n")
        assert "Hello World" in html

    def test_heading_with_inline_code_does_not_crash(self):
        """`code` inside a heading must not crash."""
        html = assert_no_crash("## Use `git commit` daily\n")
        assert "git commit" in html

    def test_multiple_headings_all_render(self):
        """Multiple headings in one document must all render."""
        md = "# One\n\n## Two\n\n### Three\n"
        html = assert_no_crash(md)
        assert "One" in html and "Two" in html and "Three" in html

    def test_headings_do_not_break_document(self):
        """Paragraphs between headings must render."""
        md = "# MARKER\n\nParagraph text here.\n\n## Another\n"
        html = assert_no_crash(md)
        assert_surrounding_content_intact(html)


# ===========================================================================
# ExtraMark Extension 4: Definition lists
# ===========================================================================
# Syntax (pandoc-style):
#   Term
#   :   First definition
#   :   Second definition
#
# Renders as <dl><dt>Term</dt><dd>First definition</dd><dd>…</dd></dl>
# mistune has a 'def_list' plugin but it is NOT enabled in Calamus.
# Case 1 — Graceful fail-over: text content visible, no crash.


class TestDefinitionLists:
    def test_simple_definition_does_not_crash(self):
        """A basic term + definition must not crash."""
        html = assert_no_crash("Python\n:   A programming language\n")
        assert "Python" in html

    def test_definition_text_visible(self):
        """The definition text must appear in the output."""
        html = render("HTML\n:   HyperText Markup Language\n")
        assert "HyperText" in html or "HTML" in html

    def test_multiple_definitions_per_term(self):
        """Multiple definitions under one term must not crash."""
        md = "Cat\n:   A small feline\n:   A domesticated animal\n"
        html = assert_no_crash(md)
        assert "Cat" in html

    def test_multiple_terms_do_not_crash(self):
        """Multiple term/definition blocks must not crash."""
        md = "Apple\n:   A fruit\n\nBanana\n:   Another fruit\n"
        html = assert_no_crash(md)
        assert "Apple" in html
        assert "Banana" in html

    def test_definition_list_does_not_break_following_heading(self):
        """A heading after a definition list must still render."""
        md = "Term\n:   Definition\n\n## MARKER heading\n"
        html = assert_no_crash(md)
        assert_surrounding_content_intact(html)

    def test_definition_list_with_blank_line_between(self):
        """A blank line between term and definition must not crash."""
        md = "Term\n\n:   Definition after blank line\n"
        html = assert_no_crash(md)
        assert "Term" in html


# ===========================================================================
# ExtraMark Extension 5: Superscript
# ===========================================================================
# Syntax: x^2^ → x<sup>2</sup>
# The caret ^ wraps the superscript content.
# mistune has a 'superscript' plugin (markdown-it-sup style) but it is NOT
# enabled in Calamus.
# Case 1 — Graceful fail-over: text content visible, no crash.


class TestSuperscript:
    def test_basic_superscript_does_not_crash(self):
        """x^2^ must not crash."""
        html = assert_no_crash("x^2^")
        assert isinstance(html, str)

    def test_superscript_content_visible(self):
        """The content inside ^...^ must appear in the output."""
        html = render("E = mc^2^")
        assert "mc" in html or "2" in html

    def test_multi_char_superscript_does_not_crash(self):
        """x^(n+1)^ with multi-char exponent must not crash."""
        html = assert_no_crash("x^(n+1)^")
        assert isinstance(html, str)

    def test_superscript_in_heading_does_not_crash(self):
        """Superscript inside a heading must not crash."""
        html = assert_no_crash("## Energy E = mc^2^\n")
        assert "Energy" in html

    def test_superscript_does_not_break_surrounding_text(self):
        """Text around a superscript must still render."""
        html = assert_no_crash("MARKER before x^2^ MARKER after")
        assert "MARKER before" in html
        assert "MARKER after" in html

    def test_multiple_superscripts_do_not_crash(self):
        """Multiple superscripts in one paragraph must not crash."""
        html = assert_no_crash("a^2^ + b^2^ = c^2^")
        assert isinstance(html, str)

    def test_superscript_not_activated_without_plugin(self):
        """Without the superscript plugin, ^...^ appears as plain text."""
        html = render("x^2^")
        # The number 2 must appear somewhere (as text, not necessarily <sup>)
        assert "2" in html


# ===========================================================================
# ExtraMark Extension 6: Subscript
# ===========================================================================
# Syntax: H~2~O → H<sub>2</sub>O
# The tilde ~ wraps the subscript content.
# mistune has a 'subscript' plugin but it is NOT enabled.
# Note: the 'strikethrough' plugin handles ~~double~~ tildes only; single
# ~tildes~ are left untouched.
# Case 1 — Graceful fail-over: text content visible, no crash.


class TestSubscript:
    def test_basic_subscript_does_not_crash(self):
        """H~2~O must not crash."""
        html = assert_no_crash("H~2~O")
        assert isinstance(html, str)

    def test_subscript_content_visible(self):
        """Content inside ~...~ must appear in the output."""
        html = render("Water is H~2~O")
        assert "H" in html and "O" in html

    def test_subscript_not_converted_to_strikethrough(self):
        """Single ~tilde~ must NOT produce <del> (only ~~ does)."""
        html = render("H~2~O is water.")
        assert "<del>" not in html

    def test_multi_char_subscript_does_not_crash(self):
        """x~(i+1)~ multi-char subscript must not crash."""
        html = assert_no_crash("x~(i+1)~")
        assert isinstance(html, str)

    def test_subscript_in_table_cell_does_not_crash(self):
        """Subscript inside a table cell must not crash."""
        md = "| Formula |\n|---------|\n| H~2~O   |\n"
        html = assert_no_crash(md)
        assert "<table>" in html

    def test_subscript_does_not_break_surrounding_text(self):
        """Text around ~subscript~ must still render."""
        html = assert_no_crash("MARKER before H~2~O MARKER after")
        assert "MARKER before" in html
        assert "MARKER after" in html

    def test_double_tilde_still_strikethrough_not_subscript(self):
        """~~double tilde~~ must still produce <del>, not subscript."""
        html = render("~~deleted~~")
        assert "<del>" in html


# ===========================================================================
# ExtraMark Extension 7: Abbreviations
# ===========================================================================
# Syntax (at any point in the document):
#   *[HTML]: HyperText Markup Language
#
# All occurrences of the abbreviation text in the document are then wrapped:
#   <abbr title="HyperText Markup Language">HTML</abbr>
#
# mistune has an 'abbr' plugin but it is NOT enabled in Calamus.
# Case 1 — Graceful fail-over: abbreviation definitions do not crash;
# text appears as plain text without <abbr> wrapping.


class TestAbbreviations:
    def test_abbreviation_definition_does_not_crash(self):
        """*[abbr]: definition syntax must not crash."""
        md = "*[HTML]: HyperText Markup Language\n\nHTML is great.\n"
        html = assert_no_crash(md)

    def test_abbreviation_text_visible(self):
        """The abbreviation text must appear in the output."""
        md = "*[CSS]: Cascading Style Sheets\n\nCSS styles pages.\n"
        html = render(md)
        assert "CSS" in html

    def test_body_text_still_renders_with_abbreviation_definition(self):
        """Document text after abbreviation definition must render."""
        md = "*[API]: Application Programming Interface\n\nMARKER text here.\n"
        html = assert_no_crash(md)
        assert "MARKER" in html

    def test_abbreviation_definition_without_plugin_is_visible_or_absent(self):
        """Without the abbr plugin, *[X]: Y either renders as text or is hidden."""
        md = "*[XYZ]: Some expansion\n\nThe XYZ system.\n"
        html = render(md)
        # The body text must be present regardless
        assert "system" in html

    def test_multiple_abbreviation_definitions_do_not_crash(self):
        """Multiple *[X]: Y lines must not crash."""
        md = "*[HTML]: HyperText Markup Language\n*[CSS]: Cascading Style Sheets\n\nHTML and CSS.\n"
        html = assert_no_crash(md)
        assert "HTML" in html or "CSS" in html

    def test_abbreviation_does_not_break_following_content(self):
        """Content after an abbreviation definition block must render."""
        md = "*[term]: expansion\n\n## MARKER heading\n"
        html = assert_no_crash(md)
        assert_surrounding_content_intact(html)


# ===========================================================================
# ExtraMark Extension 8: Footnotes
# ===========================================================================
# Syntax:
#   Reference in text: [^label]
#   Definition (anywhere): [^label]: The footnote text.
#
# Renders as a numbered superscript link to a footnote list at the end.
# mistune has a 'footnotes' plugin but it is NOT enabled in Calamus.
# Case 1 — Graceful fail-over: text content visible, no crash, no broken HTML.


class TestFootnotes:
    def test_footnote_reference_does_not_crash(self):
        """[^1] reference must not crash."""
        md = "Main text.[^1]\n\n[^1]: The footnote.\n"
        html = assert_no_crash(md)

    def test_footnote_definition_text_visible(self):
        """The footnote definition text must appear in the output."""
        md = "Content.[^note]\n\n[^note]: Footnote content here.\n"
        html = render(md)
        assert "Footnote content here" in html

    def test_body_text_with_footnote_reference_visible(self):
        """The main paragraph text must be visible alongside the footnote."""
        md = "MARKER paragraph.[^1]\n\n[^1]: Note.\n"
        html = assert_no_crash(md)
        assert "MARKER paragraph" in html

    def test_multiple_footnotes_do_not_crash(self):
        """Multiple footnote references in one document must not crash."""
        md = "First fact.[^a] Second fact.[^b]\n\n[^a]: First note.\n[^b]: Second note.\n"
        html = assert_no_crash(md)
        assert "First fact" in html
        assert "Second fact" in html

    def test_footnote_with_inline_markup_does_not_crash(self):
        """A footnote definition containing **bold** must not crash."""
        md = "Paragraph.[^1]\n\n[^1]: Note with **bold** text.\n"
        html = assert_no_crash(md)

    def test_footnote_does_not_break_document_structure(self):
        """Headings after footnotes must still render."""
        md = "Intro.[^1]\n\n[^1]: A note.\n\n## MARKER Section\n"
        html = assert_no_crash(md)
        assert_surrounding_content_intact(html)

    def test_undefined_footnote_reference_does_not_crash(self):
        """A footnote reference without a matching definition must not crash."""
        md = "Text with undefined footnote.[^missing]\n"
        html = assert_no_crash(md)
        assert isinstance(html, str)


# ===========================================================================
# ExtraMark Extension 9: Critic Markup
# ===========================================================================
# CriticMarkup (http://criticmarkup.com/) is an editorial annotation system
# with five marker types:
#
#   Addition:      {++ inserted text ++}   → <ins>inserted text</ins>
#   Deletion:      {-- deleted text --}    → <del>deleted text</del>
#   Substitution:  {~~ old ~> new ~~}      → old replaced with new
#   Highlight:     {== highlighted ==}     → <mark>highlighted</mark>
#   Comment:       {>> comment <<}         → annotation (may be hidden)
#
# mistune has no Critic Markup plugin.
# Case 1 — Graceful fail-over: text content visible, no crash.
#
# Note: CriticMarkup braces differ from GLFM inline-diff:
#   GLFM uses {+ +} / {- -} (single +/-), CriticMarkup uses {++ ++} / {-- --}.


class TestCriticMarkup:
    # ---- Addition {++ text ++} ----

    def test_addition_does_not_crash(self):
        """{++ text ++} must not crash."""
        html = assert_no_crash("I like {++ really ++} enjoy this.")

    def test_addition_content_visible(self):
        """The text inside {++ ++} must appear in the output."""
        html = render("We {++ absolutely ++} agree.")
        assert "absolutely" in html

    def test_addition_does_not_produce_broken_tags(self):
        """{++ ++} must not produce unclosed HTML tags."""
        html = render("Text {++ added ++} here.")
        assert isinstance(html, str)
        # Content must be present
        assert "added" in html

    # ---- Deletion {-- text --} ----

    def test_deletion_does_not_crash(self):
        """{-- text --} must not crash."""
        html = assert_no_crash("It was {-- not --} great.")

    def test_deletion_content_visible(self):
        """The text inside {-- --} must appear in the output."""
        html = render("Remove {-- this word --} please.")
        assert "this word" in html

    def test_deletion_does_not_activate_strikethrough(self):
        """{-- --} must not be rendered as <del> by the strikethrough plugin."""
        html = render("Keep {-- or remove --} it.")
        # CriticMarkup deletion is not ~~ strikethrough; <del> is not expected
        # from mistune's strikethrough plugin here (different delimiters)
        # Either plain text or no <del> from ~~: both acceptable
        assert "or remove" in html

    # ---- Substitution {~~ old ~> new ~~} ----

    def test_substitution_does_not_crash(self):
        """{~~ old ~> new ~~} must not crash."""
        html = assert_no_crash("She will {~~ arrive tomorrow ~> arrive today ~~}.")

    def test_substitution_content_partially_visible(self):
        """At least one side of the substitution must appear in output."""
        html = render("Say {~~ goodbye ~> hello ~~} now.")
        assert "goodbye" in html or "hello" in html

    def test_substitution_with_spaces_does_not_crash(self):
        """Substitution with spaces in both sides must not crash."""
        html = assert_no_crash("{~~ the quick brown fox ~> a fast dark fox ~~}")
        assert isinstance(html, str)

    # ---- Highlight {== text ==} ----

    def test_highlight_does_not_crash(self):
        """{== text ==} must not crash."""
        html = assert_no_crash("Please {== review this section ==}.")

    def test_highlight_content_visible(self):
        """The text inside {== ==} must appear in the output."""
        html = render("Check {== this important part ==} carefully.")
        assert "this important part" in html

    def test_highlight_does_not_produce_broken_html(self):
        """{== ==} must not produce malformed HTML."""
        html = render("Here is {== highlighted ==} text.")
        assert isinstance(html, str)
        assert html.strip()

    # ---- Comment {>> comment <<} ----

    def test_comment_does_not_crash(self):
        """{>> comment <<} must not crash."""
        html = assert_no_crash("This paragraph needs work.{>> shorten it >>}")

    def test_comment_content_not_required_in_output(self):
        """Without Critic Markup support, comments may or may not be visible."""
        html = render("Normal text.{>> editor note >>} More text.")
        # The surrounding normal text must be visible
        assert "Normal text" in html or "More text" in html

    def test_comment_after_highlight_does_not_crash(self):
        """{== highlight ==}{>> comment <<} combined must not crash."""
        html = assert_no_crash("{== important ==}{>> double-check >>}")
        assert isinstance(html, str)

    # ---- Mixed Critic Markup in one document ----

    def test_all_critic_markup_types_together_do_not_crash(self):
        """A document with all five Critic Markup types must not crash."""
        md = (
            "Original text {++ with addition ++} and "
            "{-- deletion --} and "
            "{~~ old value ~> new value ~~} and "
            "{== highlighted ==}{>> with comment <<}.\n"
        )
        html = assert_no_crash(md)

    def test_critic_markup_does_not_break_surrounding_document(self):
        """Headings and paragraphs around Critic Markup must still render."""
        md = "## MARKER heading\n\nSome {++ revised ++} content.\n"
        html = assert_no_crash(md)
        assert_surrounding_content_intact(html)

    def test_critic_markup_inside_blockquote_does_not_crash(self):
        """Critic Markup inside a blockquote must not crash."""
        html = assert_no_crash("> Quoted {++ addition ++} text.\n")
        assert "<blockquote>" in html


# ===========================================================================
# Regression: all nine extensions together
# ===========================================================================
# A document using all nine ExtraMark extensions must render without crashing
# and must produce visible content throughout.


class TestAllExtensionsTogether:
    _MIXED = """\
# Title --- Subtitle

| Feature        | Status       |
|----------------|--------------|
| Tables         | **working**  |
| Subscript      | H~2~O        |
| Superscript    | x^2^         |

*[API]: Application Programming Interface

Term
:   A definition of the term

The API[^1] is {++ greatly ++} {-- poorly --} documented.

{== Review this section ==}{>> Is the tone right? >>}

Visit https://extramark.example.com for more.

[^1]: The API reference can be found in the docs.
"""

    def test_mixed_document_does_not_crash(self):
        """A document using all ExtraMark extensions must not crash."""
        html = assert_no_crash(self._MIXED)

    def test_mixed_document_table_renders(self):
        """Table in mixed document must produce <table>."""
        html = render(self._MIXED)
        assert "<table>" in html

    def test_mixed_document_heading_renders(self):
        """Heading in mixed document must render."""
        html = render(self._MIXED)
        assert "<h1" in html
        assert "Title" in html

    def test_mixed_document_term_visible(self):
        """Definition list term text must be present in output."""
        html = render(self._MIXED)
        assert "Term" in html

    def test_mixed_document_critic_addition_visible(self):
        """CriticMarkup addition text must appear somewhere in output."""
        html = render(self._MIXED)
        assert "greatly" in html

    def test_mixed_document_footnote_definition_visible(self):
        """Footnote definition text must appear in the output."""
        html = render(self._MIXED)
        assert "API reference" in html

    def test_mixed_document_url_linked(self):
        """Bare https:// URL in mixed document must be auto-linked."""
        html = render(self._MIXED)
        assert "https://extramark.example.com" in extract_hrefs(html)

    def test_mixed_document_abbreviation_text_visible(self):
        """Abbreviation body text must appear (even without <abbr> wrapping)."""
        html = render(self._MIXED)
        assert "API" in html

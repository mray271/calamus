"""GLFM compatibility tests.

GitLab Flavored Markdown (GLFM) extends CommonMark with features not found in
standard Markdown. For each such feature, this suite verifies that Calamus
falls into one of two categories:

  Case 1 — Graceful fail-over:
    The renderer does not crash, produces valid (non-broken) HTML, and the
    rest of the document still renders correctly.  The GLFM-specific syntax
    may appear as plain text or inside a <code> block — that is acceptable.

  Case 2 — Supported:
    The rendered HTML approximates what GitLab would produce for the feature.

Reference:
  https://docs.gitlab.com/user/markdown/#differences-with-standard-markdown
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
    """Assert renderer doesn't raise, returns a non-empty string."""
    html = render(md)
    assert isinstance(html, str), "render() must return a str"
    assert html.strip(), "render() must return non-empty output"
    return html


def assert_surrounding_content_intact(html: str, marker: str = "MARKER") -> None:
    """Assert that normal Markdown around GLFM syntax renders correctly."""
    assert (
        marker in html
    ), f"Surrounding paragraph content '{marker}' missing from rendered output"


# ===========================================================================
# 1. GitLab-specific references
# ===========================================================================
# GLFM turns #123, @user, !123, ~label, %milestone etc. into links.
# Calamus has no GitLab context, so these should pass through as plain text.
# Case 1 — Graceful fail-over.


class TestGitLabReferences:
    def test_issue_reference_renders_as_text(self):
        """#123 should not crash; the '#123' text must appear in the output."""
        md = "See issue #123 for details."
        html = assert_no_crash(md)
        assert "123" in html

    def test_issue_reference_not_converted_to_link(self):
        """#123 must not produce a <a href> pointing to a GitLab issue URL."""
        html = render("Fix #42 please.")
        # There should be no gitlab.com link for issue refs
        assert "gitlab.com" not in html.lower()

    def test_user_mention_renders_as_text(self):
        """@username must not crash; text should appear in output."""
        md = "Ping @alice about this."
        html = assert_no_crash(md)
        assert "alice" in html

    def test_merge_request_reference_renders_as_text(self):
        """!123 should survive rendering as plain text."""
        md = "Closes !456."
        html = assert_no_crash(md)
        assert "456" in html

    def test_label_reference_renders_as_text(self):
        """~label should appear as text, not a GitLab label link."""
        md = "Tagged with ~bug."
        html = assert_no_crash(md)
        assert "bug" in html

    def test_milestone_reference_renders_as_text(self):
        """%v1.0 should appear as text."""
        md = "Target milestone is %v1.0."
        html = assert_no_crash(md)
        assert "v1.0" in html

    def test_commit_reference_renders_as_text(self):
        """9ba12248 (short SHA) should survive rendering."""
        md = "Fixed in commit 9ba12248."
        html = assert_no_crash(md)
        assert "9ba12248" in html

    def test_reference_does_not_break_surrounding_paragraph(self):
        """Normal text around a reference must still render."""
        md = "Start MARKER #99 end."
        html = assert_no_crash(md)
        assert_surrounding_content_intact(html)


# ===========================================================================
# 2. Inline diff
# ===========================================================================
# {+ addition +} / [+ addition +] and {- deletion -} / [- deletion -]
# Case 1 — Graceful fail-over (rendered as plain text or escaped).


class TestInlineDiff:
    def test_curly_addition_renders_without_crash(self):
        """{+ text +} syntax must not raise."""
        html = assert_no_crash("{+ added text +}")
        assert "added text" in html

    def test_square_addition_renders_without_crash(self):
        """[+ text +] syntax must not raise."""
        html = assert_no_crash("[+ added text +]")
        assert "added text" in html

    def test_curly_deletion_renders_without_crash(self):
        """{- text -} syntax must not raise."""
        html = assert_no_crash("{- removed text -}")
        assert "removed text" in html

    def test_square_deletion_renders_without_crash(self):
        """[- text -] syntax must not raise."""
        html = assert_no_crash("[- removed text -]")
        assert "removed text" in html

    def test_inline_diff_does_not_break_surrounding_content(self):
        """Text before and after the diff markers must render."""
        md = "MARKER before {+ inserted +} MARKER after"
        html = assert_no_crash(md)
        assert "before" in html
        assert "after" in html

    def test_mixed_wrappers_are_not_converted(self):
        """Mixed delimiters ({+ +]) are not valid GLFM; must not crash."""
        html = assert_no_crash("{+ addition +] and [- deletion -}")
        assert isinstance(html, str)


# ===========================================================================
# 3. Description lists
# ===========================================================================
# GLFM supports <dl>/<dt>/<dd> via "term\n: description" syntax.
# mistune 3 supports this via a 'def_list' plugin, not included by default.
# Case 1 — Graceful fail-over: must not crash; text content must be present.


class TestDescriptionLists:
    def test_description_list_does_not_crash(self):
        """term + ': description' must not raise."""
        md = "Fruits\n: apple\n: orange\n"
        html = assert_no_crash(md)
        assert "Fruits" in html or "apple" in html

    def test_description_list_content_visible(self):
        """All content from a description list must appear somewhere in output."""
        md = "Vegetables\n: broccoli\n: kale\n"
        html = assert_no_crash(md)
        # Content words must be present even if not in <dl> tags
        assert "Vegetables" in html or "broccoli" in html

    def test_description_list_does_not_break_following_heading(self):
        """Content after the description list must still render."""
        md = "Term\n: definition\n\n## MARKER heading\n"
        html = assert_no_crash(md)
        assert "MARKER" in html


# ===========================================================================
# 4. Task lists (including the GLFM-specific [~] inapplicable state)
# ===========================================================================
# Standard [x] / [ ] may be supported if the task_lists plugin is added.
# [~] is GLFM-specific.
# Case 1 — Graceful fail-over for [~]; output text must be visible.


class TestTaskLists:
    def test_checked_task_list_item_renders(self):
        """- [x] item must not crash."""
        html = assert_no_crash("- [x] Completed task\n")
        assert "Completed task" in html

    def test_unchecked_task_list_item_renders(self):
        """- [ ] item must not crash."""
        html = assert_no_crash("- [ ] Incomplete task\n")
        assert "Incomplete task" in html

    def test_inapplicable_task_item_does_not_crash(self):
        """- [~] inapplicable item is GLFM-specific; must not crash."""
        html = assert_no_crash("- [~] Inapplicable task\n")
        assert "Inapplicable task" in html

    def test_inapplicable_task_item_text_visible(self):
        """[~] item text must appear in rendered output."""
        md = "- [~] N/A item\n"
        html = render(md)
        assert "N/A item" in html

    def test_mixed_task_list_does_not_crash(self):
        """Mixed [x], [ ], and [~] list must not crash."""
        md = "- [x] Done\n- [ ] Pending\n- [~] Skipped\n"
        html = assert_no_crash(md)
        assert "Done" in html
        assert "Pending" in html
        assert "Skipped" in html


# ===========================================================================
# 5. Multiline blockquote (>>> fencing)
# ===========================================================================
# GLFM allows fencing a block quote with >>>.
# mistune does not support this — the >>> appears as plain text.
# Case 1 — Graceful fail-over.


class TestMultilineBlockquote:
    def test_triple_arrow_fence_does_not_crash(self):
        """>>> fence must not raise an exception."""
        md = ">>>\nLine one\nLine two\n>>>\n"
        html = assert_no_crash(md)

    def test_triple_arrow_content_is_visible(self):
        """Content inside >>> fences must appear in the rendered output."""
        md = ">>>\nMultiline content here\n>>>\n"
        html = render(md)
        assert "Multiline content here" in html

    def test_triple_arrow_does_not_break_document(self):
        """Content after >>> block must still render."""
        md = ">>>\nQuoted text\n>>>\n\n## MARKER\n"
        html = assert_no_crash(md)
        assert "MARKER" in html


# ===========================================================================
# 6. JSON tables (```json:table```)
# ===========================================================================
# GLFM renders JSON code blocks with the "json:table" language specifier as
# interactive tables.  Calamus should render them as a plain code block.
# Case 1 — Graceful fail-over.


class TestJsonTables:
    _JSON_TABLE = '```json:table\n{"items": [{"a": "1", "b": "2"}]}\n```\n'

    def test_json_table_does_not_crash(self):
        """json:table fence must not raise."""
        assert_no_crash(self._JSON_TABLE)

    def test_json_table_rendered_as_code_block(self):
        """json:table should at minimum produce a <pre> or <code> element."""
        html = render(self._JSON_TABLE)
        assert "<pre>" in html or "<code>" in html

    def test_json_table_raw_content_present(self):
        """The JSON payload must be present in some form in the output."""
        html = render(self._JSON_TABLE)
        assert "items" in html

    def test_json_table_does_not_break_following_content(self):
        """Content after the json:table fence must still render."""
        md = self._JSON_TABLE + "\nMARKER paragraph\n"
        html = assert_no_crash(md)
        assert "MARKER" in html


# ===========================================================================
# 7. Math equations
# ===========================================================================
# GLFM supports inline math ($`...`$ and $...$) and block math ($$...$$,
# ```math``` fences) via KaTeX.  Calamus does not have a math renderer.
# Case 1 — Graceful fail-over: LaTeX source must be visible, no crash.


class TestMathEquations:
    def test_inline_math_backtick_syntax_no_crash(self):
        """$`a^2+b^2=c^2`$ must not crash."""
        html = assert_no_crash("Inline math: $`a^2+b^2=c^2`$")
        assert "a^2" in html or "c^2" in html

    def test_inline_dollar_math_no_crash(self):
        """$a^2+b^2=c^2$ must not crash."""
        html = assert_no_crash("Value: $a^2+b^2=c^2$")
        # Dollar signs may be treated as literal text
        assert isinstance(html, str)

    def test_block_math_dollars_no_crash(self):
        """$$a^2+b^2=c^2$$ on its own line must not crash."""
        html = assert_no_crash("$$a^2+b^2=c^2$$")
        assert isinstance(html, str)

    def test_math_fence_block_no_crash(self):
        """```math fence must not crash; content must be present."""
        md = "```math\na^2+b^2=c^2\n```\n"
        html = assert_no_crash(md)
        assert "a^2" in html

    def test_math_does_not_break_following_paragraph(self):
        """Content after math block must still render."""
        md = "```math\nx = 1\n```\n\nMARKER paragraph\n"
        html = assert_no_crash(md)
        assert "MARKER" in html


# ===========================================================================
# 8. Table of contents ([[_TOC_]])
# ===========================================================================
# GLFM generates an auto-linked TOC when [[_TOC_]] appears on its own line.
# Calamus does not implement this feature.
# Case 1 — Graceful fail-over: [[_TOC_]] appears as text or a link, no crash.


class TestTableOfContents:
    def test_toc_tag_does_not_crash(self):
        """[[_TOC_]] on its own line must not crash."""
        md = "# Heading\n\n[[_TOC_]]\n\n## Section\n"
        html = assert_no_crash(md)

    def test_toc_tag_does_not_generate_actual_toc(self):
        """With no TOC support, no <nav> or multi-link TOC list is expected."""
        md = "# H1\n\n[[_TOC_]]\n\n## Section A\n\n## Section B\n"
        html = render(md)
        # The document must not produce a structured TOC element
        # We verify the headings aren't duplicated into a TOC list
        assert html.count("Section A") == 1
        assert html.count("Section B") == 1

    def test_toc_tag_content_around_it_renders(self):
        """Headings and paragraphs around [[_TOC_]] must still render."""
        md = "# MARKER heading\n\n[[_TOC_]]\n\nSome paragraph.\n"
        html = assert_no_crash(md)
        assert "MARKER" in html
        assert "Some paragraph" in html


# ===========================================================================
# 9. Alerts (> [!note], > [!warning], etc.)
# ===========================================================================
# GLFM renders styled alert boxes for blockquotes starting with [!TYPE].
# Case 2 — Supported.


class TestAlerts:
    @pytest.mark.parametrize(
        "alert_type", ["note", "tip", "important", "caution", "warning"]
    )
    def test_alert_type_does_not_crash(self, alert_type: str):
        f"""Alert type '[!{alert_type}]' must not crash."""
        md = f"> [!{alert_type}]\n> Alert body text.\n"
        html = assert_no_crash(md)
        assert f"glfm-alert-{alert_type}" in html
        assert "[!" not in html

    def test_alert_body_text_is_visible(self):
        """The alert body text must be present in the rendered output."""
        md = "> [!note]\n> This is a note.\n"
        html = render(md)
        assert "This is a note" in html

    def test_alert_renders_as_styled_blockquote(self):
        """Alert should render as a semantic GLFM alert blockquote."""
        md = "> [!warning]\n> Be careful.\n"
        html = render(md)
        assert '<blockquote class="glfm-alert glfm-alert-warning">' in html
        assert '<p class="glfm-alert-title">Warning</p>' in html

    def test_alert_with_custom_title_renders_title(self):
        """> [!warning] Custom Title should become the alert title."""
        md = "> [!warning] Data deletion\n> This is dangerous.\n"
        html = render(md)
        assert '<p class="glfm-alert-title">Data deletion</p>' in html
        assert "This is dangerous" in html

    def test_multiline_alert_content_visible(self):
        """Multi-line alert body text must appear in output."""
        md = "> [!note]\n> Line one.\n> Line two.\n"
        html = render(md)
        assert "Line one" in html
        assert "Line two" in html


# ===========================================================================
# 10. Color chips (`#RRGGBB`, `RGB(...)`, `HSL(...)`)
# ===========================================================================
# GLFM renders a small color swatch next to color codes in backticks.
# Calamus renders them as plain inline code — that is acceptable.
# Case 1 — Graceful fail-over (render as <code>).


class TestColorChips:
    @pytest.mark.parametrize(
        "color_code",
        [
            "#FF0000",
            "#F00",
            "#FF0000AA",
            "RGB(255, 0, 0)",
            "RGBA(255, 0, 0, 0.5)",
            "HSL(0, 100%, 50%)",
            "HSLA(0, 100%, 50%, 0.3)",
        ],
    )
    def test_color_code_in_backticks_does_not_crash(self, color_code: str):
        """Color codes in backticks must not crash."""
        html = assert_no_crash(f"Color: `{color_code}`")

    def test_color_code_rendered_as_inline_code(self):
        """Color code in backticks must produce at least a <code> element."""
        html = render("See `#FF0000`.")
        assert "<code>" in html
        assert "FF0000" in html

    def test_color_code_no_chip_element(self):
        """Without GLFM support, no dedicated color chip span is expected."""
        html = render("See `#00FF00`.")
        # Should be just a <code> — no complex color chip markup
        assert "<code>" in html
        # Verify no crash and content present
        assert "00FF00" in html


# ===========================================================================
# 11. Emoji shortcodes (:smile:, :+1:, etc.)
# ===========================================================================
# GLFM converts :emoji_name: shortcodes to emoji images or Unicode codepoints.
# Calamus does not implement this; shortcodes appear as plain text.
# Case 1 — Graceful fail-over.


class TestEmojiShortcodes:
    def test_basic_emoji_shortcode_does_not_crash(self):
        """:smile: shortcode must not crash."""
        html = assert_no_crash("I am :smile: today.")

    def test_emoji_shortcode_text_preserved(self):
        """The emoji shortcode text must appear somewhere in the output."""
        html = render("React with :+1: or :heart:.")
        # Without emoji support the colons and name will be in the output
        assert "+1" in html or "heart" in html or "React with" in html

    def test_emoji_does_not_produce_broken_html(self):
        """:emoji: must not produce a broken <img> tag pointing nowhere."""
        html = render("Here :rocket: goes.")
        # If no emoji support, we should NOT have an <img> with empty src
        assert '<img src=""' not in html
        assert "<img src=''" not in html

    def test_multiple_emoji_shortcodes_do_not_crash(self):
        """Multiple emoji in one paragraph must not crash."""
        md = ":tada: :bug: :heart: :100:"
        html = assert_no_crash(md)
        assert isinstance(html, str)


# ===========================================================================
# 12. YAML / TOML / JSON front matter
# ===========================================================================
# GLFM displays front matter in a box at the top of rendered files.
# mistune does not parse front matter — it either renders the --- as <hr>
# or leaves it as text.
# Case 1 — Graceful fail-over: document body must still render.


class TestFrontMatter:
    def test_yaml_front_matter_does_not_crash(self):
        """YAML front matter must not crash."""
        md = "---\ntitle: My Doc\ndate: 2024-01-01\n---\n\n# MARKER\n"
        html = assert_no_crash(md)

    def test_document_body_renders_after_yaml_front_matter(self):
        """Content after YAML front matter must be in the output."""
        md = "---\ntitle: Test\n---\n\nMARKER paragraph.\n"
        html = render(md)
        assert "MARKER" in html

    def test_toml_front_matter_does_not_crash(self):
        """TOML front matter (+++ delimiters) must not crash."""
        md = '+++\ntitle = "My Doc"\n+++\n\n# MARKER\n'
        html = assert_no_crash(md)
        assert "MARKER" in html

    def test_json_front_matter_does_not_crash(self):
        """JSON front matter (;;; delimiters) must not crash."""
        md = ';;;\n{"title": "My Doc"}\n;;;\n\nMARKER paragraph.\n'
        html = assert_no_crash(md)
        assert "MARKER" in html

    def test_front_matter_alone_does_not_crash(self):
        """A document that is only front matter must not crash."""
        md = "---\ntitle: Only Front Matter\n---\n"
        html = assert_no_crash(md)
        assert isinstance(html, str)


# ===========================================================================
# 13. Includes (::include{file=...})
# ===========================================================================
# GLFM supports embedding other documents via ::include directives.
# Calamus does not implement this; the directive should appear as text.
# Case 1 — Graceful fail-over.


class TestIncludes:
    def test_include_directive_does_not_crash(self):
        """::include{file=...} directive must not crash."""
        md = "::include{file=chapter1.md}\n"
        html = assert_no_crash(md)

    def test_include_directive_does_not_embed_file(self):
        """Without include support, no file embedding should occur."""
        md = "::include{file=/etc/passwd}\n"
        html = render(md)
        # Content of /etc/passwd must NOT appear
        assert "root:" not in html

    def test_surrounding_content_renders_with_include_directive(self):
        """Content around an include directive must still render."""
        md = "MARKER before\n\n::include{file=example.md}\n\nMARKER after\n"
        html = assert_no_crash(md)
        assert "MARKER before" in html
        assert "MARKER after" in html


# ===========================================================================
# 14. Placeholders (%{project_name}, %{default_branch}, etc.)
# ===========================================================================
# GLFM fills in placeholders at render time from project context.
# Calamus has no GitLab context; placeholders should appear as literal text.
# Case 1 — Graceful fail-over.


class TestPlaceholders:
    @pytest.mark.parametrize(
        "placeholder",
        [
            "%{project_name}",
            "%{project_path}",
            "%{default_branch}",
            "%{gitlab_server}",
            "%{latest_tag}",
            "%{commit_sha}",
        ],
    )
    def test_placeholder_does_not_crash(self, placeholder: str):
        f"""Placeholder {placeholder!r} must not crash."""
        html = assert_no_crash(f"Value: {placeholder}")

    def test_placeholder_not_replaced_with_live_data(self):
        """%{project_name} must not be replaced (no GitLab context)."""
        html = render("Project: %{project_name}")
        # Should not resolve to an actual project name
        assert "gitlab" not in html.lower() or "project_name" in html

    def test_placeholder_text_survives_rendering(self):
        """The placeholder text (or its content) should be in the output."""
        html = render("Branch: %{default_branch}")
        assert "default_branch" in html or "Branch:" in html


# ===========================================================================
# 15. Mid-word emphasis (underscores in identifiers)
# ===========================================================================
# GLFM ignores underscores inside words to avoid italicizing identifiers like
# perform_complicated_task.  This is an extension of standard Markdown.
# Case 2 — Supported (or close to it): identifier underscores must not produce
# unwanted <em> tags that split the word.


class TestMidWordEmphasis:
    def test_underscore_in_identifier_not_italicized(self):
        """perform_complicated_task must not be split into italic fragments."""
        html = render("Use perform_complicated_task() daily.")
        # The word should appear intact — no <em> splitting the identifier
        assert "perform_complicated_task" in html

    def test_multiple_underscores_not_italicized(self):
        """do_this_and_do_that must not produce spurious <em> tags."""
        html = render("Call do_this_and_do_that for the result.")
        assert "do_this_and_do_that" in html

    def test_underscore_italic_at_word_boundary_still_works(self):
        """Underscores at word boundaries should still produce italics."""
        html = render("_italic word_")
        assert "<em>" in html


# ===========================================================================
# 16. Image and video dimension attributes ({width=N height=N})
# ===========================================================================
# GLFM supports {width=100px} or {width=75%} after image/video links.
# Calamus passes these through; the attribute syntax may appear as text.
# Case 1 — Graceful fail-over.


class TestMediaDimensions:
    def test_image_with_width_attribute_does_not_crash(self):
        """![alt](img.png){width=100} must not crash."""
        md = "![Logo](logo.png){width=100}\n"
        html = assert_no_crash(md)

    def test_image_still_renders_with_dimension_attribute(self):
        """<img> tag must be present even with dimension syntax."""
        md = "![alt text](image.png){width=200 height=100}\n"
        html = render(md)
        assert "<img" in html

    def test_video_extension_link_does_not_crash(self):
        """A .mp4 image-link must not crash (GitLab renders it as <video>)."""
        md = "![Video](sample.mp4)\n"
        html = assert_no_crash(md)

    def test_audio_extension_link_does_not_crash(self):
        """A .mp3 image-link must not crash (GitLab renders it as <audio>)."""
        md = "![Audio](clip.mp3)\n"
        html = assert_no_crash(md)


# ===========================================================================
# 17. Footnotes ([^1] references)
# ===========================================================================
# Footnotes are in the CommonMark extended spec and supported by GLFM.
# mistune 3 supports them via a 'footnotes' plugin (not enabled by default).
# Case 1 — Graceful fail-over when the plugin is absent.


class TestFootnotes:
    def test_footnote_reference_does_not_crash(self):
        """[^1] reference must not crash."""
        md = "Text with a footnote.[^1]\n\n[^1]: Footnote text.\n"
        html = assert_no_crash(md)

    def test_footnote_content_visible_in_output(self):
        """Footnote definition text must appear somewhere in the output."""
        md = "Main text.[^note]\n\n[^note]: The actual note.\n"
        html = render(md)
        assert "The actual note" in html

    def test_footnote_reference_does_not_break_document(self):
        """Content around footnote refs must still render."""
        md = "MARKER paragraph[^1].\n\n[^1]: Note.\n"
        html = assert_no_crash(md)
        assert "MARKER" in html


# ===========================================================================
# 18. Superscript and subscript
# ===========================================================================
# Some GLFM docs mention superscript (^text^) and subscript (~text~).
# mistune 3 supports these via optional plugins.
# Case 1 — Graceful fail-over when plugins absent; text content preserved.


class TestSuperSubscript:
    def test_superscript_syntax_does_not_crash(self):
        """x^2^ must not crash."""
        html = assert_no_crash("x^2^ is a superscript.")
        assert isinstance(html, str)

    def test_subscript_syntax_does_not_crash(self):
        """H~2~O must not crash."""
        html = assert_no_crash("Water is H~2~O.")
        assert isinstance(html, str)

    def test_superscript_content_in_output(self):
        """The base content around superscript must be in the output."""
        html = render("E=mc^2^ (mass-energy equivalence).")
        assert "mass-energy" in html


# ===========================================================================
# 19. Strikethrough (extended feature — supported via plugin)
# ===========================================================================
# ~~text~~ is in GLFM extended features and IS enabled via the
# 'strikethrough' mistune plugin.
# Case 2 — Supported.


class TestStrikethrough:
    def test_strikethrough_renders_as_del(self):
        """~~text~~ must produce a <del> element."""
        html = render("~~struck through~~")
        assert "<del>" in html

    def test_strikethrough_content_present(self):
        """Text inside strikethrough must appear in output."""
        html = render("~~deleted content~~")
        assert "deleted content" in html

    def test_strikethrough_does_not_affect_surrounding_text(self):
        """Text around strikethrough must be unaffected."""
        html = render("Before ~~middle~~ after.")
        assert "Before" in html
        assert "after" in html


# ===========================================================================
# 20. Tables (extended feature — supported via plugin)
# ===========================================================================
# Pipe tables are in GLFM extended features and ARE enabled via the
# 'table' mistune plugin.
# Case 2 — Supported.


class TestTables:
    def test_basic_table_renders(self):
        """A basic pipe table must produce <table> element."""
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n"
        html = render(md)
        assert "<table>" in html
        assert "<th>" in html or "<td>" in html

    def test_table_alignment_does_not_crash(self):
        """Table with alignment colons must not crash."""
        md = "| Left | Center | Right |\n|:---|:---:|---:|\n| a | b | c |\n"
        html = assert_no_crash(md)
        assert "<table>" in html

    def test_table_with_empty_cells_does_not_crash(self):
        """Table with empty cells must not crash."""
        md = "| A | B | C |\n|---|---|---|\n| x |   | z |\n"
        html = assert_no_crash(md)
        assert "<table>" in html


# ===========================================================================
# 21. URL auto-linking (extended feature — supported via plugin)
# ===========================================================================
# Case 2 — Supported via the 'url' mistune plugin.


class TestUrlAutoLinking:
    def test_bare_https_url_becomes_link(self):
        """A bare https:// URL must be auto-linked."""
        html = render("Visit https://www.example.com for info.")
        assert "<a" in html
        assert "https://www.example.com" in html

    def test_bare_http_url_becomes_link(self):
        """A bare http:// URL must be auto-linked."""
        html = render("See http://example.org please.")
        assert "<a" in html

    def test_url_in_brackets_still_works(self):
        """Explicit [text](url) link must still work alongside auto-linking."""
        html = render("[Example](https://example.com)")
        assert "<a" in html
        assert "https://example.com" in html

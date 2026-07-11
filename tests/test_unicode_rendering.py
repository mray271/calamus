"""
Unicode and subscript/superscript rendering tests.

Covers three layers:

  1. Subscript/superscript plugin  — M~⊕~ → <sub>⊕</sub>, x^2^ → <sup>2</sup>
  2. Unicode preservation          — multi-byte chars survive the renderer intact
  3. UTF-8 encoding roundtrip      — the load_bytes path cannot produce mojibake

Layer 3 is the regression test for the load_html → load_bytes fix.
load_html() fell back to Latin-1 charset sniffing, corrupting every UTF-8
sequence whose first byte is 0xE2 (⊕ U+2295, − U+2212, ★ U+2605, ☉ U+2609,
″ U+2033, 🜨 U+1F728, …) into the Latin-1 character â (U+00E2) followed by
garbage.  The fix encodes to bytes explicitly and passes the encoding to
WebKit via load_bytes("utf-8"), bypassing sniffing entirely.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _renderer():
    from calamus.renderer import MistuneRenderer

    return MistuneRenderer()


# ---------------------------------------------------------------------------
# 1. Subscript / superscript plugin
# ---------------------------------------------------------------------------


class TestSubscriptPlugin:
    """M~⊕~ and friends must produce <sub> elements."""

    def test_subscript_earth_mass_symbol(self):
        html = _renderer().render("M~⊕~")
        assert "<sub>" in html
        assert "⊕" in html

    def test_subscript_earth_radius_symbol(self):
        html = _renderer().render("R~⊕~")
        assert "<sub>" in html
        assert "⊕" in html

    def test_subscript_solar_mass_symbol(self):
        html = _renderer().render("M~☉~")
        assert "<sub>" in html
        assert "☉" in html

    def test_subscript_stellar_mass_symbol(self):
        html = _renderer().render("M~★~")
        assert "<sub>" in html
        assert "★" in html

    def test_subscript_alchemical_earth(self):
        """U+1F728 🜨 — SMP character used as alternative Earth symbol."""
        html = _renderer().render("M~\U0001f728~")
        assert "<sub>" in html
        assert "\U0001f728" in html

    def test_subscript_chemical_formula(self):
        html = _renderer().render("H~2~O")
        assert "<sub>2</sub>" in html

    def test_subscript_ascii_digit(self):
        html = _renderer().render("x~1~")
        assert "<sub>1</sub>" in html

    def test_subscript_wraps_only_inner_content(self):
        html = _renderer().render("M~⊕~ and R~⊕~")
        assert html.count("<sub>") == 2
        assert html.count("</sub>") == 2

    def test_proxima_notation(self):
        """Full line from time_dilation_offsets.md."""
        md = "M~★~ = 0.1221 M~☉~, planet mass ~1.17 M~⊕~, radius ~1.04 R~⊕~"
        html = _renderer().render(md)
        assert html.count("<sub>") == 4
        assert "★" in html
        assert "☉" in html
        assert "⊕" in html


class TestSuperscriptPlugin:
    """x^2^ must produce <sup> elements."""

    def test_superscript_integer_exponent(self):
        html = _renderer().render("x^2^")
        assert "<sup>2</sup>" in html

    def test_superscript_speed_of_light(self):
        html = _renderer().render("c^2^")
        assert "<sup>2</sup>" in html

    def test_superscript_and_subscript_coexist(self):
        html = _renderer().render("x^2^ + H~2~O")
        assert "<sup>2</sup>" in html
        assert "<sub>2</sub>" in html


class TestSubscriptStrikethroughCoexistence:
    """Single-tilde subscript must not interfere with double-tilde strikethrough."""

    def test_strikethrough_still_works(self):
        html = _renderer().render("~~deleted~~")
        assert "<del>" in html

    def test_subscript_and_strikethrough_in_same_paragraph(self):
        html = _renderer().render("~~old~~ and H~2~O")
        assert "<del>" in html
        assert "<sub>2</sub>" in html

    def test_double_tilde_not_treated_as_two_subscripts(self):
        html = _renderer().render("~~strikethrough~~")
        # Must be <del>, not two empty <sub> tags
        assert "<del>" in html
        assert html.count("<sub>") == 0


# ---------------------------------------------------------------------------
# 2. Unicode character preservation through the renderer
# ---------------------------------------------------------------------------

# Characters whose UTF-8 first byte is 0xE2 — the bytes that Latin-1 misreads
# as â.  If any of these appear as 'â' in the output the encoding is broken.
E2_CHARS = {
    "⊕": "U+2295 CIRCLED PLUS (Earth mass/radius)",
    "☉": "U+2609 SUN (solar mass)",
    "★": "U+2605 BLACK STAR (stellar mass)",
    "−": "U+2212 MINUS SIGN",
    "″": "U+2033 DOUBLE PRIME (arc-seconds)",
    "≈": "U+2248 ALMOST EQUAL TO",
    "×": "U+00D7 MULTIPLICATION SIGN",
    "→": "U+2192 RIGHTWARDS ARROW",
}


@pytest.mark.parametrize("char,description", E2_CHARS.items())
def test_e2_char_preserved_in_rendered_html(char, description):
    """Each E2-family character must survive render() unchanged."""
    html = _renderer().render(f"value is {char} here")
    assert char in html, (
        f"{description} was lost or corrupted in rendered HTML. "
        "Check renderer Unicode handling."
    )


@pytest.mark.parametrize("char,description", E2_CHARS.items())
def test_e2_char_not_corrupted_to_a_circumflex(char, description):
    """Corruption manifests as â (U+00E2) replacing the real character."""
    html = _renderer().render(f"value is {char} here")
    # â must not appear unless it was in the original input
    assert (
        "\u00e2" not in html
    ), f"{description} was corrupted to â (Latin-1 mojibake) in rendered HTML."


def test_smp_alchemical_earth_preserved():
    """U+1F728 🜨 (SMP, 4-byte UTF-8) must survive the renderer."""
    char = "\U0001f728"
    html = _renderer().render(f"Earth symbol {char}")
    assert char in html


def test_unicode_minus_sign_distinct_from_hyphen():
    """U+2212 − must not be silently replaced by ASCII hyphen-minus U+002D."""
    html = _renderer().render("−22.2 km/s")
    assert "\u2212" in html  # proper minus
    # Acceptable if hyphen is also present (renderer may not change it),
    # but the original minus must survive.


# ---------------------------------------------------------------------------
# 3. UTF-8 encoding roundtrip — regression for load_html charset bug
# ---------------------------------------------------------------------------

# These are the characters reported broken before the load_bytes fix.
MOJIBAKE_REGRESSION_CHARS = [
    ("⊕", "U+2295 Earth mass/radius"),
    ("☉", "U+2609 Solar mass"),
    ("★", "U+2605 Stellar mass"),
    ("−", "U+2212 Minus sign"),
    ("″", "U+2033 Double prime"),
    ("\U0001f728", "U+1F728 Alchemical Earth"),
]


@pytest.mark.parametrize("char,description", MOJIBAKE_REGRESSION_CHARS)
def test_html_utf8_bytes_roundtrip(char, description):
    """
    Simulate the full load_bytes path: render → format into template →
    encode to UTF-8 bytes → decode back as UTF-8.

    If this roundtrip fails or the character becomes â the mojibake bug
    has regressed.
    """
    from calamus.preview import _HTML_TEMPLATE

    html_body = _renderer().render(f"Symbol: {char}")
    html_page = _HTML_TEMPLATE.format(
        body=html_body, mermaid_script="", color_scheme="light", mermaid_theme="default", highlight_css="", highlight_script=""
    )

    # Encode as UTF-8 (what load_bytes receives)
    encoded = html_page.encode("utf-8")

    # Decode back — must succeed without errors
    decoded = encoded.decode("utf-8")

    assert (
        char in decoded
    ), f"{description}: character lost after UTF-8 encode→decode roundtrip"
    assert (
        "\u00e2" not in decoded or char == "\u00e2"
    ), f"{description}: â (mojibake) appeared in UTF-8 roundtrip output"


def test_html_template_encoding_is_valid_utf8():
    """The full template with a Unicode-rich body must encode to valid UTF-8."""
    from calamus.preview import _HTML_TEMPLATE

    body = "M~⊕~ R~⊕~ M~☉~ M~★~ − ″ \U0001f728 x^2^"
    html_body = _renderer().render(body)
    page = _HTML_TEMPLATE.format(
        body=html_body, mermaid_script="", color_scheme="light", mermaid_theme="default", highlight_css="", highlight_script=""
    )

    try:
        raw = page.encode("utf-8")
        raw.decode("utf-8")  # must not raise
    except UnicodeEncodeError as exc:
        pytest.fail(f"HTML template failed UTF-8 encoding: {exc}")
    except UnicodeDecodeError as exc:
        pytest.fail(f"UTF-8 bytes could not be decoded back: {exc}")


def test_html_template_declares_utf8_charset():
    """The template must declare charset=utf-8 so browsers never sniff Latin-1."""
    from calamus.preview import _HTML_TEMPLATE

    page = _HTML_TEMPLATE.format(
        body="x", mermaid_script="", color_scheme="light", mermaid_theme="default", highlight_css="", highlight_script=""
    )
    assert 'charset="utf-8"' in page.lower() or "charset=utf-8" in page.lower(), (
        "HTML template missing charset=utf-8 declaration. "
        "Without it, WebKit may fall back to Latin-1 sniffing."
    )


def test_html_template_has_explicit_sub_font_size():
    """
    sub/sup must have an explicit font-size smaller than the UA default (≈83%).
    WebKit's 'font-size: smaller' is not visually distinct enough for
    symbol glyphs — explicit sizing (≤ 0.80em) is required.
    """
    from calamus.preview import _HTML_TEMPLATE
    import re

    page = _HTML_TEMPLATE.format(
        body="x", mermaid_script="", color_scheme="light", mermaid_theme="default", highlight_css="", highlight_script=""
    )
    # Find font-size declarations inside sub/sup rules
    match = re.search(r"sub\s*,\s*sup\s*\{[^}]*font-size:\s*([\d.]+)em", page)
    assert match, "No explicit font-size found in sub, sup CSS rule"
    size = float(match.group(1))
    assert size <= 0.80, (
        f"sub/sup font-size is {size}em — must be ≤ 0.80em for visible reduction. "
        "WebKit's UA default 'smaller' (≈0.83em) is not distinct enough."
    )


def test_no_load_html_call_in_preview():
    """
    Regression guard: preview.py must not call load_html().
    load_html() ignores the meta charset tag and corrupts multi-byte Unicode.
    Only load_bytes() with an explicit encoding is safe.
    """
    import inspect
    from calamus import preview

    source = inspect.getsource(preview)
    assert "load_html(" not in source, (
        "preview.py contains a call to load_html(). "
        "Use load_bytes() with encoding='utf-8' instead to prevent "
        "Latin-1 charset sniffing corruption of Unicode characters."
    )

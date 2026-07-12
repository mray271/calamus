"""Unit tests for calamus.__init__ constants."""


def test_version_is_string():
    from calamus import __version__

    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_mermaid_version():
    from calamus import MERMAID_VERSION

    assert MERMAID_VERSION == "11.5.0"


def test_mermaid_cdn_url():
    from calamus import MERMAID_CDN_URL, MERMAID_VERSION

    assert MERMAID_VERSION in MERMAID_CDN_URL
    assert MERMAID_CDN_URL.startswith("https://")
    assert "mermaid.min.js" in MERMAID_CDN_URL


def test_version_fallback_when_package_not_found(monkeypatch):
    import importlib
    import importlib.metadata
    import sys

    original_calamus = sys.modules.get("calamus")

    def raise_not_found(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", raise_not_found)
    sys.modules.pop("calamus", None)
    try:
        import calamus

        assert calamus.__version__ == "0.1.0-dev"
    finally:
        sys.modules.pop("calamus", None)
        if original_calamus is not None:
            sys.modules["calamus"] = original_calamus

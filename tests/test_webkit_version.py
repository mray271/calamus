"""Tests for WebKit version detection."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from calamus import webkit_version


class TestDetectWebKitVersion:
    """Test version detection logic."""

    def test_detect_webkit_6_0_when_available(self):
        """Should detect WebKit 6.0 when available."""
        with patch("calamus.webkit_version.gi.require_version") as mock_require:
            # Mock: 6.0 is available, 4.1 raises ValueError
            def require_version(namespace, version):
                if version == "6.0":
                    return None
                elif version == "4.1":
                    raise ValueError("4.1 not available")

            mock_require.side_effect = require_version
            result = webkit_version.detect_webkit_version()
            assert result == (6, 0)
            mock_require.assert_any_call("WebKit", "6.0")

    def test_detect_webkit_4_1_fallback(self):
        """Should fall back to WebKit 4.1 when 6.0 not available."""
        with patch("calamus.webkit_version.gi.require_version") as mock_require:
            # Mock: 6.0 raises ValueError, 4.1 is available
            def require_version(namespace, version):
                if version == "6.0":
                    raise ValueError("6.0 not available")
                elif version == "4.1":
                    return None

            mock_require.side_effect = require_version
            result = webkit_version.detect_webkit_version()
            assert result == (4, 1)

    def test_detect_webkit_4_1_logs_warning(self, caplog):
        """Should log deprecation warning when WebKit 4.1 detected."""
        with caplog.at_level(logging.WARNING):
            with patch("calamus.webkit_version.gi.require_version") as mock_require:

                def require_version(namespace, version):
                    if version == "6.0":
                        raise ValueError("6.0 not available")
                    elif version == "4.1":
                        return None

                mock_require.side_effect = require_version
                result = webkit_version.detect_webkit_version()

            assert result == (4, 1)
            assert any(
                "WebKit 4.1" in record.message and "EOL" in record.message
                for record in caplog.records
            )
            assert any("Aug 31, 2023" in record.message for record in caplog.records)

    def test_detect_no_webkit_available(self):
        """Should return None when no WebKit version available."""
        with patch("calamus.webkit_version.gi.require_version") as mock_require:
            # Mock: both raise ValueError
            mock_require.side_effect = ValueError("WebKit not available")
            result = webkit_version.detect_webkit_version()
            assert result is None

    def test_detect_tries_6_0_first(self):
        """Should try WebKit 6.0 before 4.1."""
        with patch("calamus.webkit_version.gi.require_version") as mock_require:
            mock_require.side_effect = ValueError("Not available")
            webkit_version.detect_webkit_version()

            calls = [call[0] for call in mock_require.call_args_list]
            # First call should be 6.0, second should be 4.1
            assert calls[0] == ("WebKit", "6.0")
            assert calls[1] == ("WebKit", "4.1")

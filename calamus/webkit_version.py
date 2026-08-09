"""WebKit version detection utilities.

Simple helper to detect which WebKit version is available.
Used for direct instantiation of appropriate preview classes.

Current support:
  - WebKit 6.0+ (fully supported)
  - WebKit 4.1 (EOL as of Aug 31, 2023 - graceful degradation only)
"""

import logging

import gi

_logger = logging.getLogger(__name__)


def detect_webkit_version() -> tuple[int, int] | None:
    """Detect installed WebKit version.

    Returns:
        Tuple of (major, minor) version numbers, or None if WebKit not available.
    """
    try:
        gi.require_version("WebKit", "6.0")
        return (6, 0)
    except ValueError:
        pass

    try:
        gi.require_version("WebKit", "4.1")
        _logger.warning(
            "WebKit 4.1 detected but is EOL (end-of-life as of Aug 31, 2023). "
            "Please upgrade to WebKit 6.0+ for ongoing support and security updates."
        )
        return (4, 1)
    except ValueError:
        pass

    return None

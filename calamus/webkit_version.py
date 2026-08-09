"""WebKit version detection utilities.

Simple helper to detect which WebKit version is available.
Used for direct instantiation of appropriate preview classes.
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
        return (4, 1)
    except ValueError:
        pass

    return None

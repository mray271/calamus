"""WebKit version detection utilities.

Simple helper to detect which WebKit version is available.
Used for direct instantiation of appropriate preview classes.

ARCHITECTURE & EOL PATTERN:
  When a new WebKit version is released, the pattern is:

  1. Create calamus/webkit_preview_Nx.py (copy from latest, update APIs)
  2. Update detect_webkit_version() to try N.x first (add before current version)
  3. Add logging.warning() for deprecated versions (e.g., "6.0 EOL [date]")
  4. Update tabs.py to handle version N (add new elif branch)
  5. Keep old implementations until official EOL

  When an old version reaches EOL:

  1. Remove from detect_webkit_version() completely
  2. Remove elif branch from tabs.py that instantiates it
  3. Delete the old calamus/webkit_preview_Nx.py file (atomic removal)
  4. Update all CI Dockerfiles to remove old WebKit packages
  5. One clean commit removes all traces

  This ABC pattern enables graceful, isolated deprecation with zero
  conditional logic scattered throughout the codebase.

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

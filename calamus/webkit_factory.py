"""Factory for creating appropriate WebKit preview implementation.

This module provides a factory function that detects the installed WebKit
version and returns the appropriate preview implementation:
  - WebKitPreview_6x for WebKit 6.0+
  - WebKitPreview_4x for WebKit 4.1 (once implemented)

The factory handles version detection and fallback strategies.
"""

import logging
from collections.abc import Callable

import gi

from calamus.renderer import AbstractMarkdownRenderer
from calamus.webkit_preview_base import AbstractWebKitPreview

_logger = logging.getLogger(__name__)

# Try to import version-specific implementations
_WEBKIT_VERSION = None
_webkit_6x_available = False
_webkit_4x_available = False

try:
    gi.require_version("WebKit", "6.0")
    from calamus.webkit_preview_6x import WebKitPreview_6x
    
    _webkit_6x_available = True
    _WEBKIT_VERSION = (6, 0)
except (ImportError, ValueError):
    pass

try:
    gi.require_version("WebKit", "4.1")
    # WebKit 4.1 implementation will be imported here once created
    # from calamus.webkit_preview_4x import WebKitPreview_4x
    # _webkit_4x_available = True
    pass
except (ImportError, ValueError):
    pass


def detect_webkit_version() -> tuple[int, int] | None:
    """Detect installed WebKit version.

    Returns:
        Tuple of (major, minor) version numbers, or None if WebKit not available.
    """
    if _WEBKIT_VERSION:
        return _WEBKIT_VERSION
    
    # Try to detect via gi.repository
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


def create_preview(
    renderer: AbstractMarkdownRenderer | None = None,
    on_open_path: Callable[[str], None] | None = None,
    on_link_hover: Callable[[str], None] | None = None,
) -> AbstractWebKitPreview:
    """Factory function to create appropriate preview implementation.

    Detects WebKit version and returns the matching implementation.
    Raises RuntimeError if no compatible WebKit is available.

    Args:
        renderer: Optional custom markdown renderer.
        on_open_path: Optional callback for file link clicks.
        on_link_hover: Optional callback for link hover events.

    Returns:
        AbstractWebKitPreview instance (WebKitPreview_6x, 4x, etc).

    Raises:
        RuntimeError: If no compatible WebKit installation found.
    """
    version = detect_webkit_version()
    
    if version is None:
        raise RuntimeError(
            "WebKit not available. Install webkitgtk6.0 or webkitgtk4.1"
        )
    
    major, minor = version
    
    if major >= 6:
        if not _webkit_6x_available:
            raise RuntimeError(
                "WebKit 6.0 detected but implementation not available"
            )
        _logger.debug(f"Creating WebKitPreview_6x for WebKit {major}.{minor}")
        return WebKitPreview_6x(renderer, on_open_path, on_link_hover)
    
    elif major == 4 and minor >= 1:
        # WebKitPreview_4x will be imported when implemented
        # For now, raise an error
        raise RuntimeError(
            "WebKit 4.1 support not yet implemented. Use WebKit 6.0."
        )
    
    else:
        raise RuntimeError(
            f"WebKit {major}.{minor} not supported. "
            "Requires WebKit 4.1+ or 6.0+"
        )

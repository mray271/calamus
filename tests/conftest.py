"""pytest configuration — stubs for optional native dependencies.

``mistune`` is a pure-Python package installed in the Docker image but not in
the host venv (dependencies are managed by uv inside the container).  Any test
that imports a calamus module whose import chain touches ``calamus.renderer``
would fail with ``ModuleNotFoundError`` on the host without this stub.

The stub is a ``MagicMock`` — sufficient for import-time attribute access and
for tests that never call the rendering code paths.  When mistune IS installed
(e.g. inside Docker), it is imported for real so rendering tests produce
actual HTML rather than MagicMock objects.
"""

import sys
from unittest.mock import MagicMock

if "mistune" not in sys.modules:
    try:
        import mistune  # noqa: F401 — import into sys.modules if available
    except ModuleNotFoundError:
        sys.modules["mistune"] = MagicMock()

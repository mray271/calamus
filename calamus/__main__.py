"""Entry point for running calamus as a module: python -m calamus"""

from __future__ import annotations

import sys


def main() -> int:
    from calamus.app import CalamusApplication

    app = CalamusApplication()
    try:
        return app.run(sys.argv)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)

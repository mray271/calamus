"""Entry point for running calamus as a module: python -m calamus"""

from __future__ import annotations

import sys


def main() -> int:
    from calamus.app import CalamusApplication

    app = CalamusApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())

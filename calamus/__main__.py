"""Entry point for running calamus as a module: python -m calamus"""

import sys
from calamus.app import CalamusApplication


def main() -> int:
    app = CalamusApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())

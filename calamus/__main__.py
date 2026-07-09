"""Entry point for running calamus as a module: python -m calamus"""

from __future__ import annotations

import os
import sys


def parse_args(
    argv: list[str],
    stdin_is_tty: bool = True,
    read_stdin: object = None,
) -> tuple[str | None, list[str], list[str]]:
    """Parse CLI arguments before handing control to GTK.

    Returns:
        pipe_content:  Text read from stdin, or ``None`` if not in pipe mode.
        initial_files: Absolute paths of files to open on startup.
        gtk_argv:      Remaining argv to pass to ``Gio.Application.run()``.

    Raises:
        SystemExit(1): if a positional argument is not an existing file.
    """
    if read_stdin is None:
        read_stdin = sys.stdin.read

    pipe_content: str | None = None
    initial_files: list[str] = []
    gtk_argv: list[str] = [argv[0]]

    for arg in argv[1:]:
        if arg == "--pipe":
            pipe_content = read_stdin()
        elif not arg.startswith("-"):
            path = os.path.abspath(arg)
            if not os.path.isfile(path):
                print(f"calamus: file not found: {arg}", file=sys.stderr)
                raise SystemExit(1)
            initial_files.append(path)
        else:
            gtk_argv.append(arg)

    # Auto-detect piped stdin only when no explicit files or --pipe given.
    if pipe_content is None and not initial_files and not stdin_is_tty:
        pipe_content = read_stdin()

    return pipe_content, initial_files, gtk_argv


def main() -> int:
    from calamus.app import CalamusApplication

    stdin_is_tty = sys.stdin.isatty()
    pipe_content, initial_files, gtk_argv = parse_args(
        sys.argv, stdin_is_tty=stdin_is_tty
    )
    app = CalamusApplication(pipe_content=pipe_content, initial_files=initial_files)
    return app.run(gtk_argv)


if __name__ == "__main__":
    sys.exit(main())

"""CalamusApplication — the top-level Gtk.Application."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib

from calamus.theme import ThemeManager
from calamus.window import CalamusWindow


class CalamusApplication(Adw.Application):
    """Primary application object."""

    def __init__(self) -> None:
        super().__init__(
            application_id="io.github.calamus.Calamus",
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )
        # When adding options here (or via add_main_option_entries /
        # add_option_group), update resources/completions/{bash,zsh,fish}/
        # and docs/calamus.1.
        # test_completion_sync.py enforces this automatically.
        self.add_main_option(
            "preview",
            "p",
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Preview mode",
            None,
        )
        self.add_main_option(
            "pipe-base-path",
            "\x00",
            GLib.OptionFlags.NONE,
            GLib.OptionArg.STRING,
            "Base path for resolving relative links in piped input",
            "PATH",
        )
        GLib.set_application_name("Calamus")
        GLib.set_prgname("calamus")
        self._theme_manager: ThemeManager | None = None
        self._pipe_content: str | None = None
        self._pipe_base_path: str | None = None
        self._initial_files: list[str] = []
        self._preview_mode: bool = False

    # ------------------------------------------------------------------
    # GApplication option / file hooks
    # ------------------------------------------------------------------

    def do_handle_local_options(self, options: GLib.VariantDict) -> int:
        pipe_base_path = None
        if options.contains("pipe-base-path"):
            value = options.lookup_value("pipe-base-path", None)
            if value is not None:
                pipe_base_path = value.get_string()
        return self._handle_options(
            preview=options.contains("preview"),
            pipe_base_path=pipe_base_path,
            argv=sys.argv,
        )

    def do_open(self, files: list, n_files: int, hint: str) -> None:
        self._initial_files = [
            os.path.abspath(f.get_path()) for f in files if f.get_path() is not None
        ]
        self.activate()

    def do_activate(self) -> None:
        self._maybe_read_piped_stdin(sys.stdin.isatty())

        if self._theme_manager is None:
            self._theme_manager = ThemeManager()

        window = self.get_active_window()
        if window is None:
            window = CalamusWindow(
                application=self,
                theme_manager=self._theme_manager,
                pipe_content=self._pipe_content,
                pipe_base_path=self._pipe_base_path,
                initial_files=self._initial_files,
                preview_mode=self._preview_mode,
            )
        window.present()

    # ------------------------------------------------------------------
    # Testable helpers (pure Python, no display required)
    # ------------------------------------------------------------------

    def _handle_options(
        self,
        preview: bool,
        pipe_base_path: str | None,
        argv: list[str],
    ) -> int:
        """Apply parsed CLI flags. Returns GApplication exit code (-1 = continue)."""
        value_options = {"--pipe-base-path"}
        i = 1
        while i < len(argv):
            arg = argv[i]
            if arg in value_options:
                i += 2
                continue
            if any(arg.startswith(f"{opt}=") for opt in value_options):
                i += 1
                continue
            if not arg.startswith("-"):
                path = os.path.abspath(arg)
                if not os.path.isfile(path):
                    print(f"calamus: file not found: {arg}", file=sys.stderr)
                    return 1
            i += 1

        if preview:
            self._preview_mode = True

        if pipe_base_path is not None:
            resolved = os.path.abspath(pipe_base_path)
            if not (os.path.isdir(resolved) or os.path.isfile(resolved)):
                print(
                    f"calamus: pipe base path not found: {pipe_base_path}",
                    file=sys.stderr,
                )
                return 1
            self._pipe_base_path = resolved

        return -1

    def _maybe_read_piped_stdin(
        self,
        stdin_is_tty: bool,
        read_stdin: Callable[[], str] | None = None,
    ) -> None:
        """Auto-detect piped stdin when no files or --pipe flag were given.

        Guards against Docker/non-TTY environments where stdin is /dev/null or
        an empty pipe: only enters pipe mode when stdin actually contains content.
        """
        if self._pipe_content is not None or self._initial_files or stdin_is_tty:
            return
        if read_stdin is None:
            read_stdin = sys.stdin.read
        content = read_stdin()
        if content:
            self._pipe_content = content

"""Tests for ThemeManager color scheme management.

Covers two user-facing scenarios:

1. **In-app override via hamburger menu** View → Color Scheme.
   The menu item activates ``app.color-scheme`` (a stateful ``Gio.SimpleAction``
   with a string variant) which calls ``ThemeManager.set_scheme()``.  These
   tests exercise ``ThemeManager`` directly with a mock ``Adw.StyleManager`` so
   no display is required.

2. **System-wide gsettings change**: ``gsettings set
   org.gnome.desktop.interface color-scheme prefer-dark``.
   Unit tests call ``_on_gsettings_changed`` directly.  An optional integration
   test exercises the full D-Bus delivery path and is skipped automatically when
   no D-Bus session is available (e.g. the CI ``test`` service which uses only
   Xvfb).
"""

from __future__ import annotations

import configparser
import os
import subprocess
from unittest.mock import MagicMock, call, patch

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib

from calamus.preferences import AbstractConfigProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MemoryConfigProvider(AbstractConfigProvider):
    """In-memory config provider — no disk I/O required during tests."""

    def __init__(self, scheme: str = "system") -> None:
        self._config = configparser.ConfigParser()
        self._config["Appearance"] = {"color_scheme": scheme}

    def load(self) -> configparser.ConfigParser:
        return self._config

    def save(self, config: configparser.ConfigParser) -> None:
        self._config = config

    def get_config_path(self) -> str:
        return ":memory:"


def _make_mock_style_manager(dark: bool = False) -> MagicMock:
    mock = MagicMock(spec=Adw.StyleManager)
    mock.get_dark.return_value = dark
    return mock


def _make_theme_manager(scheme: str = "system", dark: bool = False):
    """Return (ThemeManager, MemoryConfigProvider, mock_style_manager).

    Gio.Settings.new is patched so the test never needs a D-Bus session.
    """
    from calamus.theme import ThemeManager

    config_provider = MemoryConfigProvider(scheme)
    style_manager = _make_mock_style_manager(dark)
    with patch("calamus.theme.Gio.Settings") as mock_settings_cls:
        mock_settings_cls.new.return_value = MagicMock()
        tm = ThemeManager(
            config_provider=config_provider,
            style_manager=style_manager,
        )
    return tm, config_provider, style_manager


def _dbus_available() -> bool:
    """Return True when a working D-Bus session is reachable."""
    addr = os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")
    if not addr:
        return False
    # Socket path is after "unix:path=" and before the first comma/end.
    if addr.startswith("unix:path="):
        socket_path = addr[len("unix:path=") :].split(",")[0]
        return os.path.exists(socket_path)
    # autolaunch: or other schemes — assume available.
    return True


# ---------------------------------------------------------------------------
# 1. Initialisation
# ---------------------------------------------------------------------------


class TestThemeManagerInit:
    def test_reads_scheme_from_config(self):
        tm, _, _ = _make_theme_manager(scheme="dark")
        assert tm.get_scheme() == "dark"

    def test_defaults_to_system_when_config_missing(self):
        tm, _, _ = _make_theme_manager(scheme="system")
        assert tm.get_scheme() == "system"

    def test_invalid_config_value_falls_back_to_system(self):
        from calamus.theme import ThemeManager

        config_provider = MemoryConfigProvider(scheme="bogus")
        style_manager = _make_mock_style_manager()
        with patch("calamus.theme.Gio.Settings"):
            tm = ThemeManager(
                config_provider=config_provider,
                style_manager=style_manager,
            )
        assert tm.get_scheme() == "system"

    def test_applies_scheme_to_style_manager_at_startup(self):
        from calamus.theme import ThemeManager

        _, _, style_manager = _make_theme_manager(scheme="dark")
        style_manager.set_color_scheme.assert_called_once_with(
            Adw.ColorScheme.FORCE_DARK
        )


# ---------------------------------------------------------------------------
# 2. Hamburger menu / in-app scheme changes (View → Color Scheme)
# ---------------------------------------------------------------------------


class TestSetScheme:
    """Simulates the hamburger menu View → Color Scheme action.

    The menu item activates ``app.color-scheme`` with a string target
    (``"system"``, ``"light"``, or ``"dark"``), which calls
    ``ThemeManager.set_scheme()``.
    """

    @pytest.mark.parametrize(
        "scheme, expected_adw",
        [
            ("system", Adw.ColorScheme.DEFAULT),
            ("light", Adw.ColorScheme.FORCE_LIGHT),
            ("dark", Adw.ColorScheme.FORCE_DARK),
        ],
    )
    def test_set_scheme_applies_correct_adw_color_scheme(self, scheme, expected_adw):
        tm, _, style_manager = _make_theme_manager()
        style_manager.reset_mock()

        tm.set_scheme(scheme)

        style_manager.set_color_scheme.assert_called_once_with(expected_adw)

    @pytest.mark.parametrize("scheme", ["system", "light", "dark"])
    def test_set_scheme_persists_to_config(self, scheme):
        tm, config_provider, _ = _make_theme_manager()

        tm.set_scheme(scheme)

        saved = config_provider.load().get("Appearance", "color_scheme")
        assert saved == scheme

    @pytest.mark.parametrize("scheme", ["system", "light", "dark"])
    def test_get_scheme_reflects_change(self, scheme):
        tm, _, _ = _make_theme_manager()

        tm.set_scheme(scheme)

        assert tm.get_scheme() == scheme

    def test_set_scheme_invalid_raises_value_error(self):
        tm, _, _ = _make_theme_manager()

        with pytest.raises(ValueError, match="Invalid scheme"):
            tm.set_scheme("rainbow")

    def test_switching_dark_then_light_applies_both(self):
        tm, _, style_manager = _make_theme_manager()
        style_manager.reset_mock()

        tm.set_scheme("dark")
        tm.set_scheme("light")

        assert style_manager.set_color_scheme.call_args_list == [
            call(Adw.ColorScheme.FORCE_DARK),
            call(Adw.ColorScheme.FORCE_LIGHT),
        ]
        assert tm.get_scheme() == "light"


# ---------------------------------------------------------------------------
# 3. gsettings signal handling
# ---------------------------------------------------------------------------


class TestGsettingsSignalHandler:
    """Tests for ``_on_gsettings_changed``.

    When scheme is ``"system"``, ``Adw.StyleManager`` is already set to
    ``DEFAULT`` and follows gsettings automatically — no extra
    ``set_color_scheme`` call is needed (or expected) from the handler.
    When scheme is ``"dark"`` or ``"light"``, the user's explicit override
    takes precedence and the handler must NOT change the StyleManager.
    """

    def test_handler_does_not_call_set_color_scheme_when_system(self):
        tm, _, style_manager = _make_theme_manager(scheme="system")
        style_manager.reset_mock()

        tm._on_gsettings_changed(MagicMock(), "color-scheme")

        style_manager.set_color_scheme.assert_not_called()

    def test_handler_does_not_override_explicit_dark_scheme(self):
        tm, _, style_manager = _make_theme_manager(scheme="dark")
        style_manager.reset_mock()

        tm._on_gsettings_changed(MagicMock(), "color-scheme")

        style_manager.set_color_scheme.assert_not_called()

    def test_handler_does_not_override_explicit_light_scheme(self):
        tm, _, style_manager = _make_theme_manager(scheme="light")
        style_manager.reset_mock()

        tm._on_gsettings_changed(MagicMock(), "color-scheme")

        style_manager.set_color_scheme.assert_not_called()

    def test_gsettings_connection_attempted_on_init(self):
        from calamus.theme import ThemeManager

        config_provider = MemoryConfigProvider()
        style_manager = _make_mock_style_manager()
        with patch("calamus.theme.Gio.Settings") as mock_settings_cls:
            mock_instance = MagicMock()
            mock_settings_cls.new.return_value = mock_instance
            ThemeManager(
                config_provider=config_provider,
                style_manager=style_manager,
            )
        mock_settings_cls.new.assert_called_once_with("org.gnome.desktop.interface")
        mock_instance.connect.assert_called_once_with(
            "changed::color-scheme", mock_instance.connect.call_args[0][1]
        )

    def test_gsettings_connection_failure_does_not_crash(self):
        import warnings

        from calamus.theme import ThemeManager

        config_provider = MemoryConfigProvider()
        style_manager = _make_mock_style_manager()
        with patch("calamus.theme.Gio.Settings") as mock_settings_cls:
            mock_settings_cls.new.side_effect = GLib.Error(
                "dbus not available", "GDBus.Error", 1
            )
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                tm = ThemeManager(
                    config_provider=config_provider,
                    style_manager=style_manager,
                )
        assert tm is not None, "ThemeManager must not raise when dbus is absent"
        assert any(
            "gsettings" in str(w.message).lower() for w in caught
        ), "Expected a RuntimeWarning mentioning gsettings"


# ---------------------------------------------------------------------------
# 4. Integration test — full D-Bus signal delivery
#    Skipped automatically when no D-Bus session is available.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _dbus_available(),
    reason="D-Bus session not available (run inside Docker with dbus started by entrypoint)",
)
class TestGsettingsSignalIntegration:
    """Full-stack test: gsettings subprocess → D-Bus → Gio.Settings signal.

    Simulates what happens when a user runs::

        gsettings set org.gnome.desktop.interface color-scheme prefer-dark

    on their Fedora desktop (or inside the developer Docker container after
    ``source /tmp/dbus-env``).
    """

    def _reset_color_scheme(self):
        subprocess.run(
            [
                "gsettings",
                "set",
                "org.gnome.desktop.interface",
                "color-scheme",
                "default",
            ],
            check=True,
        )
        # Drain pending signals.
        for _ in range(5):
            GLib.MainContext.default().iteration(False)

    def test_gsettings_set_prefer_dark_delivers_signal(self):
        received: list[str] = []

        settings = Gio.Settings.new("org.gnome.desktop.interface")
        settings.connect(
            "changed::color-scheme",
            lambda _s, key: received.append(key),
        )

        self._reset_color_scheme()
        received.clear()

        subprocess.run(
            [
                "gsettings",
                "set",
                "org.gnome.desktop.interface",
                "color-scheme",
                "prefer-dark",
            ],
            check=True,
        )

        # Pump the GLib main loop until the signal arrives or we time out.
        for _ in range(50):
            GLib.MainContext.default().iteration(False)
            if received:
                break

        assert "color-scheme" in received, (
            "changed::color-scheme signal was not delivered after "
            "`gsettings set ... prefer-dark`"
        )

    def test_gsettings_set_default_delivers_signal(self):
        received: list[str] = []

        # Start from prefer-dark so switching to default is a real change.
        subprocess.run(
            [
                "gsettings",
                "set",
                "org.gnome.desktop.interface",
                "color-scheme",
                "prefer-dark",
            ],
            check=True,
        )
        for _ in range(10):
            GLib.MainContext.default().iteration(False)

        settings = Gio.Settings.new("org.gnome.desktop.interface")
        settings.connect(
            "changed::color-scheme",
            lambda _s, key: received.append(key),
        )
        received.clear()

        subprocess.run(
            [
                "gsettings",
                "set",
                "org.gnome.desktop.interface",
                "color-scheme",
                "default",
            ],
            check=True,
        )

        for _ in range(50):
            GLib.MainContext.default().iteration(False)
            if received:
                break

        assert "color-scheme" in received, (
            "changed::color-scheme signal was not delivered after "
            "`gsettings set ... default`"
        )
        # Cleanup
        self._reset_color_scheme()

    def test_theme_manager_system_scheme_follows_gsettings(self):
        """ThemeManager with scheme='system' must reflect gsettings dark state."""
        from calamus.theme import ThemeManager

        # Use real Adw.StyleManager (requires display — available via Xvfb or host).
        try:
            tm = ThemeManager(config_provider=MemoryConfigProvider("system"))
        except Exception as exc:
            pytest.skip(f"Could not create real ThemeManager: {exc}")

        subprocess.run(
            [
                "gsettings",
                "set",
                "org.gnome.desktop.interface",
                "color-scheme",
                "prefer-dark",
            ],
            check=True,
        )
        for _ in range(50):
            GLib.MainContext.default().iteration(False)

        assert (
            tm.get_dark() is True
        ), "ThemeManager.get_dark() should be True after gsettings prefer-dark"

        subprocess.run(
            [
                "gsettings",
                "set",
                "org.gnome.desktop.interface",
                "color-scheme",
                "default",
            ],
            check=True,
        )
        for _ in range(50):
            GLib.MainContext.default().iteration(False)

        assert (
            tm.get_dark() is False
        ), "ThemeManager.get_dark() should be False after gsettings default"

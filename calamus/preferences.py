"""Preferences dialog and configuration management."""

from __future__ import annotations

from abc import ABC, abstractmethod
import configparser
import os

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

CONFIG_DIR = os.path.expanduser("~/.config/Calamus")
CONFIG_FILE = os.path.join(CONFIG_DIR, "Calamus.conf")

DEFAULTS: dict[str, dict[str, str]] = {
    "Editor": {
        "font_family": "Monospace",
        "font_size": "11",
        "tab_width": "4",
        "use_spaces": "true",
        "show_line_numbers": "true",
        "word_wrap": "true",
        "highlight_current_line": "true",
    },
    "Preview": {
        "auto_refresh": "true",
        "refresh_delay_ms": "500",
    },
    "Appearance": {
        "color_scheme": "system",
    },
    "Export": {
        "default_export_dir": "",
    },
    "Files": {
        "remember_recent": "true",
        "max_recent": "10",
        "default_open_dir": "",
    },
    "RecentFiles": {},
}


class AbstractConfigProvider(ABC):
    """Defines configuration persistence behavior."""

    @abstractmethod
    def load(self) -> configparser.ConfigParser:
        """Load application configuration."""

    @abstractmethod
    def save(self, config: configparser.ConfigParser) -> None:
        """Persist application configuration."""

    @abstractmethod
    def get_config_path(self) -> str:
        """Return the configuration file path."""


class FileConfigProvider(AbstractConfigProvider):
    """File-backed config provider."""

    def __init__(self, config_path: str | None = None) -> None:
        self._config_path = config_path or CONFIG_FILE

    def load(self) -> configparser.ConfigParser:
        config = configparser.ConfigParser()
        for section, values in DEFAULTS.items():
            config[section] = dict(values)
        if os.path.exists(self._config_path):
            config.read(self._config_path)
        for section, values in DEFAULTS.items():
            if not config.has_section(section):
                config[section] = dict(values)
            for key, value in values.items():
                config[section].setdefault(key, value)
        return config

    def save(self, config: configparser.ConfigParser) -> None:
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        for section, values in DEFAULTS.items():
            if not config.has_section(section):
                config[section] = dict(values)
            for key, value in values.items():
                config[section].setdefault(key, value)
        with open(self._config_path, "w", encoding="utf-8") as handle:
            config.write(handle)

    def get_config_path(self) -> str:
        return self._config_path


def save_config(config: configparser.ConfigParser) -> None:
    """Save configuration to CONFIG_FILE, silently ignoring permission errors."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as handle:
            config.write(handle)
    except (PermissionError, OSError):
        pass


class PreferencesDialog(Adw.PreferencesWindow):
    """Preferences UI backed by an abstract config provider."""

    def __init__(
        self,
        config_provider: AbstractConfigProvider | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.set_title("Preferences")
        self.set_default_size(600, 500)
        self._config_provider = config_provider or FileConfigProvider()
        self._config = self._config_provider.load()
        self._build_ui()

    def _build_ui(self) -> None:
        editor_page = Adw.PreferencesPage.new()
        editor_page.set_title("Editor")
        editor_page.set_icon_name("document-edit-symbolic")
        self.add(editor_page)

        editor_group = Adw.PreferencesGroup.new()
        editor_group.set_title("Editing")
        editor_page.add(editor_group)

        font_row = Adw.SpinRow.new_with_range(8, 32, 1)
        font_row.set_title("Font Size")
        font_row.set_value(self._config.getint("Editor", "font_size", fallback=11))
        editor_group.add(font_row)

        tab_row = Adw.SpinRow.new_with_range(2, 8, 1)
        tab_row.set_title("Tab Width")
        tab_row.set_value(self._config.getint("Editor", "tab_width", fallback=4))
        editor_group.add(tab_row)

        spaces_row = Adw.SwitchRow.new()
        spaces_row.set_title("Insert Spaces Instead of Tabs")
        spaces_row.set_active(
            self._config.getboolean("Editor", "use_spaces", fallback=True)
        )
        editor_group.add(spaces_row)

        lineno_row = Adw.SwitchRow.new()
        lineno_row.set_title("Show Line Numbers")
        lineno_row.set_active(
            self._config.getboolean("Editor", "show_line_numbers", fallback=True)
        )
        editor_group.add(lineno_row)

        wrap_row = Adw.SwitchRow.new()
        wrap_row.set_title("Word Wrap")
        wrap_row.set_active(
            self._config.getboolean("Editor", "word_wrap", fallback=True)
        )
        editor_group.add(wrap_row)

        appearance_page = Adw.PreferencesPage.new()
        appearance_page.set_title("Appearance")
        appearance_page.set_icon_name("applications-graphics-symbolic")
        self.add(appearance_page)

        appearance_group = Adw.PreferencesGroup.new()
        appearance_group.set_title("Theme")
        appearance_page.add(appearance_group)

        theme_row = Adw.ComboRow.new()
        theme_row.set_title("Color Scheme")
        theme_row.set_model(Gtk.StringList.new(["System", "Light", "Dark"]))
        scheme = self._config.get("Appearance", "color_scheme", fallback="system")
        theme_row.set_selected({"system": 0, "light": 1, "dark": 2}.get(scheme, 0))
        appearance_group.add(theme_row)

        self._font_row = font_row
        self._tab_row = tab_row
        self._spaces_row = spaces_row
        self._lineno_row = lineno_row
        self._wrap_row = wrap_row
        self._theme_row = theme_row

        self.connect("close-request", self._on_close)

    def _on_close(self, *_args: object) -> bool:
        self._save()
        return False

    def _save(self) -> None:
        self._config["Editor"]["font_size"] = str(int(self._font_row.get_value()))
        self._config["Editor"]["tab_width"] = str(int(self._tab_row.get_value()))
        self._config["Editor"]["use_spaces"] = str(
            self._spaces_row.get_active()
        ).lower()
        self._config["Editor"]["show_line_numbers"] = str(
            self._lineno_row.get_active()
        ).lower()
        self._config["Editor"]["word_wrap"] = str(self._wrap_row.get_active()).lower()
        schemes = ["system", "light", "dark"]
        self._config["Appearance"]["color_scheme"] = schemes[
            self._theme_row.get_selected()
        ]
        self._config_provider.save(self._config)

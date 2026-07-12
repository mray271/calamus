"""Unit tests for calamus.preferences."""

import os

from calamus.preferences import FileConfigProvider


def test_load_config_defaults(tmp_path):
    provider = FileConfigProvider(str(tmp_path / "Calamus.conf"))
    config = provider.load()
    assert config.get("Editor", "font_size") == "11"
    assert config.get("Editor", "tab_width") == "4"
    assert config.getboolean("Editor", "use_spaces") is True


def test_save_and_reload_config(tmp_path):
    config_path = str(tmp_path / "Calamus.conf")
    provider = FileConfigProvider(config_path)
    config = provider.load()
    config["Editor"]["font_size"] = "14"
    provider.save(config)
    config2 = provider.load()
    assert config2.get("Editor", "font_size") == "14"


def test_load_reads_existing_config_file(tmp_path):
    import configparser

    config_path = str(tmp_path / "Calamus.conf")
    cfg = configparser.ConfigParser()
    cfg["Editor"] = {"font_size": "16"}
    with open(config_path, "w") as f:
        cfg.write(f)
    provider = FileConfigProvider(config_path)
    config = provider.load()
    assert config.get("Editor", "font_size") == "16"


def test_get_config_path(tmp_path):
    path = str(tmp_path / "Calamus.conf")
    provider = FileConfigProvider(path)
    assert provider.get_config_path() == path


def test_save_config_writes_file(tmp_path, monkeypatch):
    import configparser

    import calamus.preferences as prefs

    config_file = str(tmp_path / "Calamus.conf")
    monkeypatch.setattr(prefs, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(prefs, "CONFIG_FILE", config_file)

    config = configparser.ConfigParser()
    config["Editor"] = {"font_size": "12"}
    prefs.save_config(config)

    assert os.path.exists(config_file)


def test_save_config_ignores_permission_error(tmp_path, monkeypatch):
    import configparser

    import calamus.preferences as prefs

    monkeypatch.setattr(prefs, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(prefs, "CONFIG_FILE", str(tmp_path / "Calamus.conf"))
    monkeypatch.setattr(prefs.os, "makedirs", lambda *args, **kwargs: None)

    def fail_open(*args, **kwargs):
        raise PermissionError("read-only")

    monkeypatch.setattr("builtins.open", fail_open)

    config = configparser.ConfigParser()
    config["Editor"] = {"font_size": "12"}
    prefs.save_config(config)

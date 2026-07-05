"""Unit tests for calamus.preferences."""

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

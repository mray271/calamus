"""Unit tests for calamus.recentfiles."""

from calamus.preferences import FileConfigProvider
from calamus.recentfiles import ConfigFileRecentFilesProvider


def test_add_and_get(tmp_path):
    provider = FileConfigProvider(str(tmp_path / "Calamus.conf"))
    recent = ConfigFileRecentFilesProvider(provider)
    files = []
    for i in range(3):
        file_path = tmp_path / f"file{i}.md"
        file_path.write_text("# test", encoding="utf-8")
        files.append(str(file_path))
    for file_path in files:
        recent.add(file_path)
    result = recent.get_list()
    assert result[0] == files[-1]
    assert len(result) == 3


def test_max_recent(tmp_path):
    provider = FileConfigProvider(str(tmp_path / "Calamus.conf"))
    config = provider.load()
    config["Files"]["max_recent"] = "3"
    provider.save(config)
    recent = ConfigFileRecentFilesProvider(provider)
    files = []
    for i in range(5):
        file_path = tmp_path / f"file{i}.md"
        file_path.write_text("# test", encoding="utf-8")
        files.append(str(file_path))
    for file_path in files:
        recent.add(file_path)
    assert len(ConfigFileRecentFilesProvider(provider).get_list()) <= 3


def test_no_duplicates(tmp_path):
    provider = FileConfigProvider(str(tmp_path / "Calamus.conf"))
    recent = ConfigFileRecentFilesProvider(provider)
    file_path = tmp_path / "file.md"
    file_path.write_text("# test", encoding="utf-8")
    recent.add(str(file_path))
    recent.add(str(file_path))
    result = ConfigFileRecentFilesProvider(provider).get_list()
    assert result.count(str(file_path)) == 1


def test_clear(tmp_path):
    provider = FileConfigProvider(str(tmp_path / "Calamus.conf"))
    recent = ConfigFileRecentFilesProvider(provider)
    file_path = tmp_path / "file.md"
    file_path.write_text("# test", encoding="utf-8")
    recent.add(str(file_path))
    recent.clear()
    assert ConfigFileRecentFilesProvider(provider).get_list() == []

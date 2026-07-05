"""Recent files provider implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
import os

from calamus.preferences import AbstractConfigProvider, FileConfigProvider


class AbstractRecentFilesProvider(ABC):
    """Defines recent-file persistence behavior."""

    @abstractmethod
    def add(self, path: str) -> None:
        """Add a path to the recent files list."""

    @abstractmethod
    def get_list(self) -> list[str]:
        """Return the recent file list."""

    @abstractmethod
    def clear(self) -> None:
        """Clear the recent file list."""

    @abstractmethod
    def get_max_recent(self) -> int:
        """Return the maximum number of stored recent files."""


class ConfigFileRecentFilesProvider(AbstractRecentFilesProvider):
    """Config-file backed recent files provider."""

    def __init__(
        self,
        config_provider: AbstractConfigProvider | None = None,
    ) -> None:
        self._config_provider = config_provider or FileConfigProvider()

    def add(self, path: str) -> None:
        config = self._config_provider.load()
        absolute_path = os.path.abspath(path)
        files = self._get_list(config)
        if absolute_path in files:
            files.remove(absolute_path)
        files.insert(0, absolute_path)
        config["RecentFiles"] = {
            str(index): value
            for index, value in enumerate(files[: self.get_max_recent()])
        }
        self._config_provider.save(config)

    def get_list(self) -> list[str]:
        config = self._config_provider.load()
        return [path for path in self._get_list(config) if os.path.exists(path)]

    def clear(self) -> None:
        config = self._config_provider.load()
        config["RecentFiles"] = {}
        self._config_provider.save(config)

    def get_max_recent(self) -> int:
        config = self._config_provider.load()
        return config.getint("Files", "max_recent", fallback=10)

    def _get_list(self, config) -> list[str]:
        if not config.has_section("RecentFiles"):
            return []
        return [
            config["RecentFiles"][key]
            for key in sorted(config["RecentFiles"].keys(), key=int)
            if config["RecentFiles"][key]
        ]

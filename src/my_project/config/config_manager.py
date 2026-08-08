import json
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from my_project.config.models import (
    ComicsRootConfig,
    ComicVineConfig,
    Config,
    DatabaseConfig,
    UIConfig,
)
from my_project.utils.paths import APP_DATA_DIR


class ConfigManager(QObject):
    comics_root_changed = Signal(Path)
    api_key_changed = Signal(str)

    def __init__(self, json_path: Path | None = None) -> None:
        if json_path:
            self._config_path = json_path
        else:
            self._config_path = APP_DATA_DIR / "config.json"
        self._config: Config | None = None

    @property
    def config(self) -> Config:
        if self._config is None:
            self.load()

        return self._config  # type: ignore

    def update_settings(self, comics_root: Path, api_key: str) -> None:
        changed_root = comics_root != self.config.comicsroot.path
        changed_key = api_key != self.config.comicvine.api_key

        self.config.comicsroot.path = comics_root
        self.config.comicvine.api_key = api_key

        self.save()

        if changed_root:
            self.comics_root_changed.emit(comics_root)

        if changed_key:
            self.api_key_changed.emit(api_key)

    def load(self) -> Config:
        if not self._config_path.exists():
            self._config = self._default_config()
            self.save()

        with self._config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self._config = Config(
            database=DatabaseConfig(path=Path(data["database"]["path"])),
            comicvine=ComicVineConfig(api_key=data["comicvine"]["api_key"]),
            comicsroot=ComicsRootConfig(path=Path(data["comicsroot"]["path"])),
            ui=UIConfig(**data["ui"]),
        )

        return self._config

    def save(self) -> None:
        if self._config is None:
            raise RuntimeError("No configuration has been loaded.")

        data = asdict(self._config)

        data["database"]["path"] = str(self._config.database.path)
        data["comicsroot"]["path"] = str(self._config.comicsroot.path)

        with self._config_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    def _default_config(self) -> Config:
        return Config(
            database=DatabaseConfig(path=APP_DATA_DIR / "comics.db"),
            comicsroot=ComicsRootConfig(Path("")),
            comicvine=ComicVineConfig(""),
            ui=UIConfig(""),
        )

from dataclasses import dataclass
from pathlib import Path


@dataclass
class DatabaseConfig:
    path: Path


@dataclass
class ComicsRootConfig:
    path: Path


@dataclass
class ComicVineConfig:
    api_key: str


@dataclass
class UIConfig:
    theme: str


@dataclass
class Config:
    database: DatabaseConfig
    comicsroot: ComicsRootConfig
    comicvine: ComicVineConfig
    ui: UIConfig


# def default_config(db_path: Path) -> Config:
#     return Config(
#         database=DatabaseConfig(db_path),
#         comicsroot=ComicsRootConfig(Path("")),
#         comicvine=ComicVineConfig(""),
#         ui=UIConfig("dark"),
#     )

# def write_to_config_file(contents):
#     with CONFIG_PATH.open("w", encoding="utf-8") as f:
#         json.dump(
#             asdict(contents),
#             f,
#             indent=4,
#         )

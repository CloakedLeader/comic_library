import os
from pathlib import Path

APP_NAME = "ComicLibrary"


def get_app_data_dir() -> Path:
    """Return the directory used for ComicLibrary user data."""
    if os.name == "nt":
        app_data = os.environ.get("APPDATA")
        if not app_data:
            raise RuntimeError("APPDATA environment variable is not set.")
        path = Path(app_data) / APP_NAME
    else:
        # Useful if you ever run the application on Linux.
        path = Path.home() / ".local" / "share" / APP_NAME

    path.mkdir(parents=True, exist_ok=True)
    return path


APP_DATA_DIR = get_app_data_dir()

ENV_PATH = APP_DATA_DIR / ".env"
DB_PATH = APP_DATA_DIR / "comics.db"
CACHE_DIR = APP_DATA_DIR / "cache"
LOG_DIR = APP_DATA_DIR / "logs"

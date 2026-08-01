"""
Collection of scripts to ensure database integrity and all the key assests
can be contacted and are working.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from my_project.database.db_setup import create_tables, insert_roles


def ensure_env_and_db() -> Path:
    """
    Makes sure the environment variable file contains the database filepath.
    Then calls a function to make sure the database exists.
    """
    project_root = Path(__file__).resolve().parents[3]
    # base_dir = Path(__file__).resolve().parent
    env_path = project_root / ".env"

    if not env_path.exists():
        default_db = project_root / "comics.db"
        env_path.write_text(f"DB_PATH={default_db}\n")
        return ensure_db_exists(default_db)

    load_dotenv(env_path, override=True)

    raw_db_path = os.getenv("DB_PATH")

    if not raw_db_path:
        default_db = project_root / "comics.db"

        with env_path.open("a") as f:
            f.write(f"DB_PATH={default_db}\n")

        return ensure_db_exists(default_db)

    db_path = Path(raw_db_path).expanduser()
    return ensure_db_exists(db_path)


def ensure_db_exists(db_path: Path | str) -> Path:
    """
    Ensures that the database exists in the path given in the argument.

    Args:
        db_path (Path | str): The filepath for the database, taken from
            either the environment variable or created next to main.py.

    Returns:
        Path: The filepath for the database.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.touch(exist_ok=True)
    return db_path


def startup_checks() -> None:
    """
    Accumulates all the database health checks into one function.
    """
    db_path = ensure_env_and_db()
    create_tables(db_path)
    insert_roles(db_path)

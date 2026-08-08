"""
Collection of scripts to ensure database integrity and all the key assests
can be contacted and are working.
"""

from pathlib import Path

from my_project.config.config_manager import ConfigManager
from my_project.database.db_setup import create_tables, insert_roles


def ensure_database(config_manager: ConfigManager) -> Path:
    return ensure_db_exists(config_manager.config.database.path)


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


def startup_checks(config_manager: ConfigManager) -> None:
    """
    Accumulates all the database health checks into one function.
    """
    db_path = config_manager.config.database.path
    create_tables(db_path)
    insert_roles(db_path)

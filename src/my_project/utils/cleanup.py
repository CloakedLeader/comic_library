import logging
import os
import sqlite3
from pathlib import Path
from typing import overload

from my_project.config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


@overload
def delete_comic(identifier: str, cursor, config_man: ConfigManager) -> None: ...


@overload
def delete_comic(identifier: Path, cursor, config_man: ConfigManager) -> None: ...


def delete_comic(identifier: Path | str, cursor, config_man: ConfigManager) -> None:
    if type(identifier) == Path:
        cursor.execute("SELECT id FROM comics where file_path = ?", (str(identifier),))
        results = cursor.fetchone()
        if not results:
            print("No matching comic")
            return None
        primary_key = results[0]
    else:
        primary_key = identifier
    cover_dir = config_man.comics_root / ".covers"
    for suffix in ["_t.jpg", "_b.jpg"]:
        cover_file = cover_dir / f"{primary_key}{suffix}"
        if cover_file.exists():
            cover_file.unlink()

    cursor.execute("DELETE FROM comics WHERE id = ?", (primary_key,))
    print("Deleted main comic.")

    tables = {
        "comic_characters",
        "comic_creators",
        "comic_teams",
        "comics_fts5",
        "favourites",
        "ratings",
        "reading_progress",
        "reviews",
    }
    for table in tables:
        cursor.execute(
            f"DELETE FROM {table} WHERE comic_id = ?",
            (primary_key,),  # nosec B608
        )

    print("Deleted all orphan references")

    return None


def scan_and_clean(config_man: ConfigManager) -> None:
    conn = sqlite3.connect(config_man.config.database.path)
    cursor = conn.cursor()

    if not config_man.has_comics_root:
        return

    cursor.execute("SELECT id, file_path FROM comics")
    rows = cursor.fetchall()
    missing = []
    for comic_id, partial_file_path in rows:
        full_file_path = config_man.comics_root / Path(partial_file_path)
        if not os.path.exists(full_file_path):
            missing.append((comic_id, Path(partial_file_path)))
    if len(missing) == 0:
        logger.info("Comic database is up to date.")
        return None
    for _, relative_file_path in missing:
        logger.info(
            "Removing missing comic: " f"{config_man.comics_root / relative_file_path}"
        )
        delete_comic(relative_file_path, cursor, config_man)
    conn.commit()

    logger.info(f"Scan complete. Removed {len(missing)} missing comics.")
    conn.close()
    return None

import os
import sqlite3
from pathlib import Path
import logging

from dotenv import load_dotenv

load_dotenv()
root_folder = os.getenv("ROOT_DIR") or ""
ROOT_DIR = Path(root_folder)

logging.basicConfig(
    filename="debug.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def delete_comic(filepath: str) -> None:
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM comics where file_path = ?", (filepath,))
    results = cursor.fetchone()
    if not results:
        return None
    primary_key = results[0]
    cover_dir = ROOT_DIR / ".covers"
    for suffix in ["_t.jpg", "_b.jpg"]:
        cover_file = cover_dir / f"{primary_key}{suffix}"
        if cover_file.exists():
            cover_file.unlink()

    cursor.execute("DELETE FROM comics WHERE id = ?", (primary_key,))

    tables = {
        "comic_characters",
        "comic_creators",
        "comic_teams",
        "comics_fts5",
        "favourites",
        "reading_progress",
        "reviews",
    }
    for table in tables:
        cursor.execute(
            f"DELETE FROM {table} WHERE comic_id = ?",
            (primary_key,),  # nosec B608
        )

    conn.commit()
    conn.close()
    return None


def scan_and_clean() -> None:
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id, file_path FROM comics")
    rows = cursor.fetchall()
    missing = []
    for comic_id, file_path in rows:
        if not os.path.exists(file_path):
            missing.append((comic_id, file_path))
    if len(missing) == 0:
        logging.info("Comic database is up to date.")
        return None
    for _, file_path in missing:
        logging.debug(f"Removing missing comic: {file_path}")
        delete_comic(file_path)

    logging.info(f"Scan complete. Removed {len(missing)} missing comics.")
    return None


def clean_orphans() -> None:
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM comics")
    existing_ids = {row[0] for row in cursor.fetchall()}

    # Find all tables in the DB
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]

    total_removed = 0
    for table in tables:
        # Check if table has a comic_id column
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        if "comic_id" in columns:
            # Delete rows where comic_id is not in comics table
            cursor.execute(f"SELECT comic_id FROM {table}")
            table_ids = [row[0] for row in cursor.fetchall()]
            orphan_ids = [cid for cid in table_ids if cid not in existing_ids]
            if orphan_ids:
                cursor.executemany(
                    f"DELETE FROM {table} WHERE comic_id = ?",
                    [(oid,) for oid in orphan_ids],
                )
                total_removed += len(orphan_ids)
                logging.info(f"Removed {len(orphan_ids)} orphan references from {table}")

    conn.commit()
    conn.close()
    logging.info(f"Cleanup complete. Total orphan references removed: {total_removed}")

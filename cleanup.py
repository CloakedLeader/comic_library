import os
import sqlite3
from pathlib import Path


def delete_comic(filepath: str) -> None:
    base_dir = Path("D:/adams-comics")

    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM comics where file_path = ?", (filepath,))
    results = cursor.fetchone()
    if not results:
        return None
    primary_key = results[0]
    cover_dir = base_dir / ".covers"
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
            f"DELETE FROM {table} WHERE comic_id = ?", (primary_key,)  # nosec B608
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
        print("Comic database is up to date.")
        return None
    for _, file_path in missing:
        print(f"Removing missing comic: {file_path}")
        delete_comic(file_path)

    print(f"Scan complete. Removed {len(missing)} missing comics.")
    return None

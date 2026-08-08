import logging
import os
import sqlite3
from pathlib import Path

from my_project.config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class Cleanup:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager

    def __enter__(self):
        """
        Enters the context manager by connecting to the database and initialising the
        context manager.
        """
        self.conn = sqlite3.connect(self.config_manager.config.database.path)
        self.cursor = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exits the context manager by saving the changes to the database and closing the connection"""
        self.conn.commit()
        self.conn.close()
        return

    def delete_comic(self, filepath: Path) -> None:
        self.cursor.execute(
            "SELECT id FROM comics where file_path = ?", (str(filepath),)
        )
        results = self.cursor.fetchone()
        if not results:
            return None
        primary_key = results[0]
        cover_dir = self.config_manager.config.comicsroot.path / ".covers"
        for suffix in ["_t.jpg", "_b.jpg"]:
            cover_file = cover_dir / f"{primary_key}{suffix}"
            if cover_file.exists():
                cover_file.unlink()

        self.cursor.execute("DELETE FROM comics WHERE id = ?", (primary_key,))

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
            self.cursor.execute(
                f"DELETE FROM {table} WHERE comic_id = ?",
                (primary_key,),  # nosec B608
            )

        return None

    def scan_and_clean(self) -> None:
        self.cursor.execute("SELECT id, file_path FROM comics")
        rows = self.cursor.fetchall()
        missing = []
        for comic_id, partial_file_path in rows:
            full_file_path = self.config_manager.config.comicsroot.path / Path(
                partial_file_path
            )
            if not os.path.exists(full_file_path):
                missing.append((comic_id, full_file_path))
        if len(missing) == 0:
            logger.info("Comic database is up to date.")
            return None
        for _, file_path in missing:
            logger.info(f"Removing missing comic: {file_path}")
            self.delete_comic(file_path)

        logger.info(f"Scan complete. Removed {len(missing)} missing comics.")
        return None

    def clean_orphans(self) -> None:
        self.cursor.execute("SELECT id FROM comics")
        existing_ids = {row[0] for row in self.cursor.fetchall()}

        # Find all tables in the DB
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in self.cursor.fetchall()]

        total_removed = 0
        for table in tables:
            # Check if table has a comic_id column
            self.cursor.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in self.cursor.fetchall()]
            if "comic_id" in columns:
                # Delete rows where comic_id is not in comics table
                self.cursor.execute(f"SELECT comic_id FROM {table}")
                table_ids = [row[0] for row in self.cursor.fetchall()]
                orphan_ids = [cid for cid in table_ids if cid not in existing_ids]
                if orphan_ids:
                    self.cursor.executemany(
                        f"DELETE FROM {table} WHERE comic_id = ?",
                        [(oid,) for oid in orphan_ids],
                    )
                    total_removed += len(orphan_ids)
                    logger.info(
                        f"Removed {len(orphan_ids)} orphan references from {table}"
                    )
        logger.info(
            f"Cleanup complete. Total orphan references removed: {total_removed}"
        )

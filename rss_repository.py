import sqlite3
from datetime import datetime, timezone
from typing import Any


class RSSRepository:
    """
    Class for managing RSS feed entries in an SQLite database.

    This class provides methods for storing, retrieving and managing
    RSS feed entries with automatic cleanup of old entries.
    """

    def __init__(self, db_file: str) -> None:
        """
        Initialise the RSS repository with a database connection.

        Args:
            db_file: Path to the SQLite database file.
        """
        self.connection = sqlite3.connect(db_file)
        self.cursor = self.connection.cursor()

    def insert_entries(self, entries: list[dict[str, Any]]) -> None:
        """
        Insert multiple RSS entries using an "insert of ignore"
        strategy.

        Args:
            entries: List of dictionaries containing RSS entry data.

        Each dictionary should contain:
            - link: Entry URL
            - title: Entry title
            - pub_date: Publication date
            - summary: Entry summary
            - cover_link: Cover image URL
        """
        sql = """
            INSERT OR IGNORE INTO rss_entries (url, title,
            pub_epoch, summary, cover_url)
            VALUES (:link, :title, :pub_date, :summary, :cover_link )
            """
        self.cursor.executemany(sql, entries)
        self.connection.commit()

    def delete_old_entries(self, lifetime: int = 14) -> None:
        """
        Delete entries older than the specified lifetime.

        Args:
            lifetime: Maximum number of days an entry survives in the
        database.

        Removes entries that are older than the specified number of days
        from the current date.
        """
        seconds_in_day = 86_400
        cutoff_epoch = (
            int(datetime.now(timezone.utc).timestamp()) - lifetime * seconds_in_day
        )
        self.cursor.execute(
            "DELETE FROM rss_entries WHERE pub_epoch < ?",
            (cutoff_epoch,),
        )
        self.connection.commit()

    def get_recent_entries(self, limit: int = 10) -> list[tuple[str, str]]:
        """
        Fetch a limited number of recent entries with title and cover URL.

        Args:
            limit: Maximum number of entries to retrieve.

        Returns:
            List of tuples containing (title, cover_url).

        Entries are ordered by publication date in descending order.
        """
        # Need to add extra data here eventually, maybe the download link
        self.cursor.execute(
            """
            SELECT url, title, cover_url
            FROM rss_entries
            WHERE pub_epoch IS NOT NULL
            ORDER BY pub_epoch DESC
            LIMIT ?
        """,
            (limit,),
        )
        return self.cursor.fetchall()

    def close(self) -> None:
        """
        Commit pending transactions and close the database connection.

        Should be called when finished with the repository to ensure
        data integrity and proper resource cleanup.
        """
        self.connection.commit()
        self.connection.close()

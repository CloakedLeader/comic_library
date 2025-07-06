import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

class RSSRepository:
    """Repository for managing RSS feed entries in an SQLite database.
    
    This class provides methods for storing, retrieving, and managing
    RSS feed entries with automatic cleanup of old entries.
    """
    def __init__(self, db_file: str) -> None:
        """Initialize the RSS repository with a database connection.
        
        Args:
            db_file: Path to the SQLite database file
        """
        self.connection = sqlite3.connect(db_file)
        self.cursor = self.connection.cursor()

    def get_latest_pub_date(self) -> Optional[str]:
        """Retrieve the latest publication date from stored entries.
        
        Returns:
            Optional[str]: The most recent publication date, or None if no entries exist
        """
        self.cursor.execute(
            "SELECT pub_date FROM rss_entries ORDER BY datetime(pub_date) DESC LIMIT 1"
        )
        row = self.cursor.fetchone()
        return row[0] if row else None
    
    def insert_entries(self, entries: list[dict[str, Any]]) -> None:
        """Insert multiple RSS entries using an "insert or ignore" strategy.
        
        Args:
            entries: List of dictionaries containing RSS entry data
            
        Each entry dictionary should contain:
            - link: Entry URL (used as primary key)
            - title: Entry title
            - pub_date: Publication date
            - summary: Entry summary
            - cover_link: Cover image URL
        """
        sql = """
            INSERT OR IGNORE INTO rss_entries (url, title, pub_date, summary, cover_url)
            VALUES (:link, :title, :pub_date, :summary, :cover_link )
            """
        self.cursor.executemany(sql, entries)
        self.connection.commit()

    def delete_old_entries(self, lifetime: int = 14) -> None:
        """Delete entries older than the specified lifetime.
        
        Args:
            lifetime: Maximum age of entries in days (default: 14)
            
        Removes entries that are older than the specified number of days
        from the current date.
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=lifetime)
        self.cursor.execute(
            "DELETE FROM rss_entries WHERE datetime(pub_date) < ?",
            (cutoff_date.strftime("%Y-%m-%d %H:%M:%S"),)
        )
        self.connection.commit()

    def get_recent_entries(self, limit: int = 10) -> list[tuple[str, str]]:
        """Fetch a limited number of recent entries with title and cover URL.
        
        Args:
            limit: Maximum number of entries to retrieve (default: 10)
            
        Returns:
            list[tuple[str, str]]: List of tuples containing (title, cover_url)
            
        Entries are ordered by publication date in descending order.
        """
        # Need to add extra data here eventually, maybe the download link
        self.cursor.execute("""
            SELECT title, cover_url
            FROM rss_entries
            ORDER BY datetime(pub_date) DESC
            LIMIT ?
        """, (limit,))
        return self.cursor.fetchall()

    def close(self) -> None:
        """Commit pending transactions and close the database connection.
        
        Should be called when finished with the repository to ensure
        data integrity and proper resource cleanup.
        """
        self.connection.commit()
        self.connection.close()
    

def init_db() -> None:
    """Initialize the database and create the rss_entries table if it doesn't exist.
    
    Creates a table with columns for URL (primary key), title, publication date,
    summary, and cover URL for storing RSS feed entries.
    """
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rss_entries (
            url TEXT PRIMARY KEY,
            title TEXT,
            pub_date TEXT,
            summary TEXT,
            cover_url TEXT
            )
                """)
    conn.commit()
    conn.close()

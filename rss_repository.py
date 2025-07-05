import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

class RSSRepository:
    def __init__(self, db_file: str) -> None:
        self.connection = sqlite3.connect(db_file)
        self.cursor = self.connection.cursor()

    def get_latest_pub_date(self) -> Optional[str]:
        self.cursor.execute(
            "SELECT pub_date FROM rss_entries ORDER BY datetime(pub_date) DESC LIMIT 1"
        )
        row = self.cursor.fetchone()
        return row[0] if row else None
    
    def insert_entries(self, entries: list[dict[str, Any]]) -> None:
        sql = """
            INSERT OR IGNORE INTO rss_entries (url, title, pub_date, summary, cover_url)
            VALUES (:link, :title, :pub_date, :summary, :cover_link )
            """
        self.cursor.executemany(sql, entries)
        self.connection.commit()

    def delete_old_entries(self, lifetime: int = 14) -> None:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=lifetime)
        self.cursor.execute(
            "DELETE FROM rss_entries WHERE datetime(pub_date) < ?",
            (cutoff_date.strftime("%Y-%m-%d %H:%M:%S"),)
        )
        self.connection.commit()

    def get_recent_entries(self, limit: int = 10) -> list[tuple[str, str]]:
        # Need to add extra data here eventually, maybe the download link
        self.cursor.execute("""
            SELECT title, cover_url
            FROM rss_entries
            ORDER BY datetime(pub_date) DESC
            LIMIT ?
        """, (limit,))
        return self.cursor.fetchall()

    def close(self) -> None:
        self.connection.commit()
        self.connection.close()
    

def init_db() -> None:
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

import sqlite3
from datetime import datetime, timedelta

DB_FILE = "comics.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rss_entries (
            url TEXT PRIMARY KEY,
            title TEXT,
            pub_date TEXT,
                   )

    """)
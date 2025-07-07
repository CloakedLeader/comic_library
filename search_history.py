import sqlite3
from datetime import datetime

def create_hist_db() -> None:
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

def add_search_history(query: str) -> None:
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO search_history (query, timestamp) 
        VALUES (?, ?)
        """, (query.strip(), datetime.now())
    )
    

"""
import sqlite3
from datetime import datetime

def add_search_history(conn, query: str):
    with conn:
        conn.execute(
            "INSERT INTO search_history (query, timestamp) VALUES (?, ?)",
            (query.strip(), datetime.now())
        )
"""
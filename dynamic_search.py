import sqlite3
from typing import Optional

def create_virtual_table() -> None:
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()
    cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS comic_search fts5(
                    title, 
                    publisher,
                    creators,
                    characters,
                    series,
                    content='comics',
                    content_rowid='id',
                    tokenize='porter'
                )
""")
    conn.commit()
    conn.close()

def flatten_comic_for_fts5(comic_id: int) -> Optional[dict]:
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT comics.title, series.name, publishers.name 
        FROM comics
        LEFT JOIN series ON series.id = comic.series
        LEFT JOIN publishers on publishers.id = comic.publisher_id
        LEFT JOIN comic_types ON comic_types.id = comics.type_id
        WHERE comics.id = ?
    """, (comic_id,))
    row = cursor.fetchone()
    if not row:
        return None

    title, series_name, publisher_name = row

    def flatten_from_junction(cursor, join_table: str, entity_table: str, entity_col: str) -> str:
        cursor.execute(f"""
            SELECT {entity_table}.name
            FROM {join_table}
            JOIN {entity_table} ON {entity_table}.id = {join_table}.{entity_col}
            WHERE {join_table}.comic_id = ?
    """, (comic_id,))
        return ", ".join(r[0] for r in cursor.fetchall())
    
    conn.close()

    characters = flatten_from_junction(cursor, "comic_characters", "characters", "characters_id")
    creators = flatten_from_junction(cursor, "comic_creators", "creators", "creator_id")

    return {
        "id": comic_id,
        "title": title or "",
        "series": series_name or "",
        "publisher": publisher_name or "",
        "characters": characters or "",
        "creators": creators or "",
    }


def index_comic_for_search(comic_id: int) -> None:
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()
    data = flatten_comic_for_fts5(comic_id)
    if data is None:
        return None
    cursor.execute("""
        INSERT INTO comic_search (rowid, title, series, publisher, characters, creators)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data["id"],
        data["title"],
        data["series"],
        data["publisher"],
        data["characters"],
        data["creators"]
    ))
    conn.commit()
    conn.close()
    return None
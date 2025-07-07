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


def search_comics(user_input: str, limit: int = 20) -> Optional[dict[str, str | int]]:
    """
    Search the fts5 database for directly matching reslts.

    Args:
    user_input: A string prefixed with a field to search in.
    limit: The maximum number of matching results to be returned.

    Returns:

    """
    query = parse_search_query(user_input)
    if not query:
        return None

    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT rowid FROM comic_search
        WHERE comic_search MATCH ?
        LIMIT ?
    """, (query, limit))

    comic_ids = [row[0] for row in cursor.fetchall()]
    if not comic_ids:
        return None

    placeholders = ",".join("?" for _ in comic_ids)

    cursor.execute(f"""
        SELECT comics.*, publishers.name AS publisher_name,
        FROM comics
        LEFT JOIN publishers ON comics.publisher_id = publisher.id
        WHERE comics.id IN ({placeholders})
    """, comic_ids)

    results = []
    colomns = [col[0] for col in cursor.description]
    for row in cursor.fetchall():
        results.append(dict(zip(colomns, row)))

    return results


def parse_search_query(user_input: str) -> str:
    """
    Takes a search query and splits it up into
    the different fields of which it involves.

    Args:
    user_input: A string of one or more queries 
    prefixed by a field indicator from field_aliases.

    Returns:
    A string which clearly declares the query data
    and their corresponding fields.

    Example::
    input: '#mutant &marvel char:wolverine creator:claremont"'
    returns:
    'tags:"mutant" AND character:"wolverine AND 
    creators:"claremont"'
    """
    field_aliases = {
        "#": "tags",
        "&": "publisher",
        "char:": "characters",
        "cre:": "creators",
        "ser:": "series",
        "gen:": "genre"
    }

    tokens = user_input.strip().split()
    terms = []
    
    for token in tokens:
        matched = False
        for prefix, field in field_aliases.items():
            if token.lower().startswith(prefix):
                value = token[len(prefix):]
                terms.append(f'{field}: "{value}"')
                matched = True
                break
        if not matched:
            terms.append(f'title: "{token}"')
    return ' AND '.join(terms)

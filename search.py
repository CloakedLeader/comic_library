import sqlite3

from helper_classes import GUIComicInfo


def text_search(text) -> list[GUIComicInfo] | None:
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, title FROM comics_fts5
        WHERE comics_fts5 MATCH ?
        """,
        (text,),
    )
    results = cursor.fetchall()
    if results is None:
        return None
    hits = []
    for result in results:
        primary_key = result[0]
        title = result[1]
        filepath = get_filepath(primary_key)
        cover_path = f"D:adams-comics//.covers//{primary_key}_b.jpg"
        if filepath is None:
            continue
        comic_info = GUIComicInfo(
            primary_id=primary_key,
            title=title,
            filepath=filepath,
            cover_path=cover_path,
        )
        hits.append(comic_info)

    return hits


def get_filepath(primary_key) -> str | None:
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()

    cursor.execute("SELECT file_path FROM comics WHERE id = ?", (primary_key,))
    results = cursor.fetchone()
    return results[0] if results is not None else None

import os
import sqlite3

from helper_classes import GUIComicInfo

DB_PATH = os.path.abspath("comics.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()


def get_and_flatten_data(comic_id: str) -> dict[str, str]:
    cursor.execute("SELECT title, series FROM comics WHERE id = ?", (comic_id,))
    title, series = cursor.fetchone()

    cursor.execute(
        """
        SELECT c.name
        FROM comic_characters AS cl
        JOIN characters AS c ON cl.character_id = c.id
        WHERE cl.comic_id = ?
        """,
        (comic_id,),
    )
    raw_characters = cursor.fetchall()

    cursor.execute(
        """
        SELECT c.real_name
        FROM comic_creators AS cc
        JOIN creators AS c ON cc.creator_id = c.id
        WHERE cc.comic_id = ? AND cc.role_id NOT IN(?, ?, ?)
        """,
        (
            comic_id,
            4,
            5,
            7,
        ),
    )
    raw_creators = cursor.fetchall()

    cursor.execute(
        """
        SELECT t.name
        FROM comic_teams AS ct
        JOIN teams AS t ON ct.team_id = t.id
        WHERE ct.comic_id = ?
        """,
        (comic_id,),
    )
    raw_teams = cursor.fetchall()

    characters = [row[0] for row in raw_characters]
    creators = [row[0] for row in raw_creators]
    teams = [row[0] for row in raw_teams]

    characters_str = " ".join(characters)
    creators_str = " ".join(creators)
    teams_str = " ".join(teams)

    return {
        "comic_id": comic_id,
        "title": title,
        "series": series,
        "creators": creators_str,
        "characters": characters_str,
        "teams": teams_str,
    }


def insert_into_fts5(cleaned_data: dict[str, str]) -> None:
    cursor.execute(
        """
        INSERT INTO comics_fts5(
        comic_id, series, title, creators, characters, teams)
        VALUES (:comic_id, :series, :title, :creators, :characters, :teams)
        """,
        cleaned_data,
    )
    conn.commit()


def text_search(text) -> list[GUIComicInfo] | None:
    cursor.execute(
        """
        SELECT comic_id, title, series FROM comics_fts5
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
        title = f"{result[1]}: {result[2]}"
        filepath = get_filepath(primary_key)
        cover_path = f"D://adams-comics//.covers//{primary_key}_b.jpg"
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
    cursor.execute("SELECT file_path FROM comics WHERE id = ?", (primary_key,))
    results = cursor.fetchone()
    return results[0] if results is not None else None

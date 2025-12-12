import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

from classes.helper_classes import GUIComicInfo

load_dotenv()
root_folder = os.getenv("ROOT_DIR")
ROOT_DIR = Path(root_folder if root_folder is not None else "")
DB_PATH = os.path.abspath("comics.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()


def get_and_flatten_data(comic_id: str) -> dict[str, str]:
    """
    Gets important metadata for a given comic and collates it into a dictionary.

    Args:
        comic_id (str): The unique ID of the comic in the database.

    Returns:
        dict[str, str]: A dictionary containing title info and character/team info.
    """    
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

    characters = [row[0] for row in raw_characters if row[0] != "MISSING"]
    creators = [row[0] for row in raw_creators if row[0] != "MISSING"]
    teams = [row[0] for row in raw_teams if row[0] != "MISSING"]

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
    """
    Takes comic metadata and inserts it into a fast search database.

    Args:
        cleaned_data (dict[str, str]): A dictionary containing the information required
            for the fast search database. Includes: id, series, title, creators, characters and teams.
    """    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO comics_fts5(
        comic_id, series, title, creators, characters, teams)
        VALUES (:comic_id, :series, :title, :creators, :characters, :teams)
        """,
        cleaned_data,
    )
    conn.commit()
    conn.close()


def text_search(text: str) -> list[GUIComicInfo] | None:
    """
    Uses a text string to search the FTS5 database. Finds any maches and collates their
    info into a GUIComicInfo and returns a list of these.

    Args:
        text (str): The user inputted search parameter.

    Returns:
        list[GUIComicInfo] | None: A list of the comics matching the search criteria, or None if none match.
    """    
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
        cover_path = ROOT_DIR / ".covers" / f"{primary_key}_b.jpg"
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


def get_filepath(primary_key: str) -> Path | None:
    """
    Uses the unique ID of the comic to query the database and get the filepath.

    Args:
        primary_key (str): The unique ID of the comic.

    Returns:
        Path | None: The filepath of the comic or None if it cannot be found.
    """    
    cursor.execute("SELECT file_path FROM comics WHERE id = ?", (primary_key,))
    results = cursor.fetchone()
    absolute_path = ROOT_DIR / Path(results[0])
    return absolute_path if results is not None else None

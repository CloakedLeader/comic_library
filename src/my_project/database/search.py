"""
A file containing functions that add to the fts5 database and query it.
"""

import sqlite3

from my_project.classes.helper_classes import GUIComicInfo
from my_project.config.config_manager import ConfigManager
from my_project.database.gui_repo_worker import RepoWorker


class FTS5Inserter:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager

    def __enter__(self):
        """
        Enters the context manager by connecting to the database and initialising the
        context manager.
        """
        self.conn = sqlite3.connect(self.config_manager.config.database.path)
        self.cursor = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exits the context manager by saving the changes to the database and closing the connection"""
        self.conn.commit()
        self.conn.close()
        return

    def get_and_flatten_data(self, comic_id: str) -> dict[str, str]:
        """
        Gets important metadata for a given comic and collates it into a dictionary.

        Args:
            comic_id (str): The unique ID of the comic in the database.

        Returns:
            dict[str, str]: A dictionary containing title info and character/team info.
        """
        self.cursor.execute(
            "SELECT title, series FROM comics WHERE id = ?", (comic_id,)
        )
        title, series = self.cursor.fetchone()

        self.cursor.execute(
            """
            SELECT c.name
            FROM comic_characters AS cl
            JOIN characters AS c ON cl.character_id = c.id
            WHERE cl.comic_id = ?
            """,
            (comic_id,),
        )
        raw_characters = self.cursor.fetchall()

        self.cursor.execute(
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
        raw_creators = self.cursor.fetchall()

        self.cursor.execute(
            """
            SELECT t.name
            FROM comic_teams AS ct
            JOIN teams AS t ON ct.team_id = t.id
            WHERE ct.comic_id = ?
            """,
            (comic_id,),
        )
        raw_teams = self.cursor.fetchall()

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

    def insert_into_fts5(self, cleaned_data: dict[str, str]) -> None:
        """
        Takes comic metadata and inserts it into a fast search database.

        Args:
            cleaned_data (dict[str, str]): A dictionary containing the information required
                for the fast search database. Includes: id, series, title, creators, characters and teams.
        """
        self.cursor.execute(
            """
            INSERT INTO comics_fts5(
            comic_id, series, title, creators, characters, teams)
            VALUES (:comic_id, :series, :title, :creators, :characters, :teams)
            """,
            cleaned_data,
        )


class FTS5Searcher:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager

    def __enter__(self):
        """
        Enters the context manager by connecting to the database and initialising the
        context manager.
        """
        self.conn = sqlite3.connect(self.config_manager.config.database.path)
        self.cursor = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exits the context manager by saving the changes to the database and closing the connection"""
        self.conn.commit()
        self.conn.close()
        return

    def text_search(self, text: str) -> list[GUIComicInfo] | None:
        """
        Uses a text string to search the FTS5 database. Finds any maches and collates their
        info into a GUIComicInfo and returns a list of these.

        Args:
            text (str): The user inputted search parameter.

        Returns:
            list[GUIComicInfo] | None: A list of the comics matching the search criteria, or None if none match.
        """
        query = " ".join(f"{term}*" for term in text.split())

        self.cursor.execute(
            """
            SELECT comic_id, title, series FROM comics_fts5
            WHERE comics_fts5 MATCH ?
            """,
            (query,),
        )
        results = self.cursor.fetchall()
        if not results:
            return None
        hits = []
        with RepoWorker(self.config_manager) as worker:
            for result in results:
                primary_key = result[0]
                title = f"{result[1]}: {result[2]}"
                filepath = worker.get_filepath(primary_key)
                cover_path = (
                    self.config_manager.config.comicsroot.path
                    / ".covers"
                    / f"{primary_key}_b.jpg"
                )
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

    def collection_search(
        self, text: str, collection_id: int
    ) -> list[GUIComicInfo] | None:
        """
        Gets all comics in the collection that are also in the collection.

        First gets all text search results for the entire database and then loops
        through each of these and only keeps the ones that are in the collection.

        Args:
            text (str): The next for the general search.
            collection_id (int): The unique identifier for the comic collecetion.

        Returns:
            list[GUIComicInfo] | None: The list of results.
        """
        basic_search = self.text_search(text)
        if basic_search is None:
            return None

        def check_in_collection(comic_id: str) -> bool:
            """Checks whether a given comic_id is in the collection from the parent function."""
            self.cursor.execute(
                """
                SELECT EXISTS(
                SELECT 1
                FROM collections_contents
                WHERE collection_id = ?
                    AND comic_id = ?)
                """,
                (collection_id, comic_id),
            )
            return self.cursor.fetchone()[0] == 1

        collection_results = []
        for result in basic_search:
            if check_in_collection(result.primary_id):
                collection_results.append(result)
            else:
                continue

        return collection_results

import sqlite3
from typing import Optional
import os


class ComicSearchEngine:
    def __init__(self, db_path: str = "comics.db") -> None:
        self.db_path = db_path
        self.cursor = self.setup_cursor()

    def setup_cursor(self):
        connection = sqlite3.connect(self.db_path)
        return connection.cursor()
    
    def flatten_comic(self, comic_id: int) -> Optional[dict[str, str]]:
        self.cursor.execute("""
            SELECT comics.title
            FROM comics
            WHERE comics.id = ?
        """, (comic_id,))
        row = self.cursor.fetchone()

        if not row:
            return None
        title, = row

        # def flatten_from_junction(join_table: str, entity_table: str, entity_col: str) -> str:
        #     self.cursor.execute(f"""
        #         SELECT {entity_table}.name
        #         FROM {join_table}
        #         JOIN {entity_table} ON {entity_table}.id = {join_table}.{entity_col}
        #         WHERE {join_table}.comic_id = ?
        #     """, (comic_id,))
        #     return ", ".join(r[0] for r in self.cursor.fetchall())

        # characters = flatten_from_junction("comic_characters", "characters", "characters_id")
        # creators = flatten_from_junction("comic_creators", "creators", "creator_id")

        return {
            "id": comic_id,
            "title": title or "",
            "series": "",
            "publisher": "",
            "characters": "",
            "creators": "",
        }

    def index_comic_for_search(self, comic_id: int) -> None:
        connection = sqlite3.connect("comics.db")
        cursor = connection.cursor()
        data = self.flatten_comic(comic_id)
        if data is None:
            return None
        cursor.execute("""
            INSERT OR REPLACE INTO comic_search (rowid, title, series, publisher, characters, creators)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data["id"],
            data["title"],
            data["series"],
            data["publisher"],
            data["characters"],
            data["creators"]
        ))
        connection.commit()
        connection.close()

    def search_comics(self, user_input: str, limit: int = 20) -> Optional[list[dict[str, str | int]]]:
        """
        Search the fts5 database for directly matching reslts.

        Args:
        user_input: A string prefixed with a field to search in.
        limit: The maximum number of matching results to be returned.

        Returns:

        """
        query = self.parse_search_query(user_input)
        if not query:
            return None

        self.cursor.execute("""
            SELECT rowid FROM comic_search
            WHERE comic_search MATCH ?
            LIMIT ?
        """, (query, limit))

        comic_ids = [row[0] for row in self.cursor.fetchall()]
        if not comic_ids:
            return None

        placeholders = ",".join("?" for _ in comic_ids)

        self.cursor.execute(f"""
            SELECT comics.*, publishers.name AS publisher_name
            FROM comics
            LEFT JOIN publishers ON comics.publisher_id = publishers.id
            WHERE comics.id IN ({placeholders})
        """, comic_ids)

        colomns = [col[0] for col in self.cursor.description]
        return [dict(zip(colomns, row)) for row in self.cursor.fetchall()]

    @staticmethod
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
    
    def index_all_comics(self):
        self.cursor.execute("SELECT id FROM comics")
        comic_ids = [row[0] for row in self.cursor.fetchall()]
        for comic_id in comic_ids:
            self.index_comic_for_search(comic_id)


def create_virtual_table() -> None:
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()
    cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS comic_search USING fts5(
                    title,
                    publisher,
                    creators,
                    characters,
                    series,
                    content_rowid='id',
                    tokenize='porter'
                )
""")
    conn.commit()
    conn.close()

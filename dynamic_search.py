import sqlite3
from typing import Optional


class ComicSearchEngine:
    def __init__(self, db_path: str = "comics.db") -> None:
        self.db_path = db_path
        self.cursor = self.setup_cursor()

    def setup_cursor(self):
        self.connection = sqlite3.connect(self.db_path)
        return self.connection.cursor()

    def get_character_names(self, comic_id: str) -> list[str]:
        self.cursor.execute(
            """
            SELECT c.name
            FROM comic_characters cc
            LEFT JOIN characters c ON cc.character_id = c.id
            WHERE cc.comic_id = ?
            """, (comic_id,)
        )
        return [row[0] for row in self.cursor.fetchall()]

    def get_creators_names(self, comic_id: str) -> list[str]:
        self.cursor.execute(
            """
            SELECT c.name
            FROM comic_creators cc
            LEFT JOIN creators c ON cc.creator_id = c.id
            WHERE cc.comic_id = ?
            """, (comic_id,)
        )
        return [row[0] for row in self.cursor.fetchall()]

    def get_publisher(self, comic_id: str) -> str:
        self.cursor.execute(
            """
            SELECT p.name
            FROM comics c
            LEFT JOIN publishers p ON c.publisher_id = p.id
            WHERE c.id = ?
            """, (comic_id,)
        )
        return self.cursor.fetchone()[0]

    def rebuild_fts5(self):
        comics = self.connection.execute("SELECT id, title FROM comics").fetchall()

        for comic in comics:
            comic_id, title = comic

            creators = self.get_creators_names(comic_id)
            creators_text = " ".join(creators)

            characters = self.get_character_names(comic_id)
            characters_text = " ".join(characters)

            publisher = self.get_publisher(comic_id).strip()

            self.cursor.execute(
                """
                INSERT INTO comic_search (rowid, title, publisher, creators, characters)
                VALUES (?, ?, ?, ?, ?)
                """,
                (comic_id, title, publisher, creators_text, characters_text)
            )
        self.connection.commit()

    def search_comics(self, user_input: str, limit: int = 20) -> Optional[list[dict]]:
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
            "&": "publisher",
            "char:": "characters",
            "cre:": "creators",
        }

        tokens = user_input.strip().split()
        terms = []

        for token in tokens:
            matched = False
            for prefix, field in field_aliases.items():
                if token.lower().startswith(prefix):
                    value = token[len(prefix):]
                    terms.append(f'{field}:{value}')
                    matched = True
                    break
            if not matched:
                terms.append(f'title:{token}')
        return ' AND '.join(terms)


def create_virtual_table() -> None:
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()
    cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS comic_search USING fts5(
                    title,
                    publisher,
                    creators,
                    characters,
                    content= '',
                    tokenize='porter'
                )
""")
    conn.commit()
    conn.close()

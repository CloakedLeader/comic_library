import sqlite3
import uuid
from typing import Optional

from helper_classes import ComicInfo


class MetadataInputting:
    def __init__(self, comicinfo_dict: ComicInfo) -> None:
        self.clean_info = comicinfo_dict

    @staticmethod
    def generate_uuid():
        return str(uuid.uuid4())

    def open_connection(self):
        self.conn = sqlite3.connect("comics.db")
        self.cursor = self.conn.cursor()

    def db_into_main_db_table(self):
        self.cursor.execute(
            """
                        INSERT INTO comics (title, series, volume_id, publisher_id,
                        release_date, file_path, description, type_id)
                        VALUES (:title, :series, :volume_num, :release_date,
                        :filepath, :description, :type_id)
                            """,
            self.clean_info,
        )
        self.conn.commit()

    def get_character_by_name(self, name: str):
        self.cursor.execute(
            """
            SELECT characters.id, characters.real_name, aliases.alias
            FROM aliases
            JOIN character_alias_links ON aliases.id = character_alias_links.alias_id
            JOIN characters ON characters.id = character_alias_links.character_id
            WHERE aliases.alias = ?
        """,
            (name,),
        )
        row = self.cursor.fetchone()
        if row:
            return row[0], row[1], row[2]

        self.cursor.execute(
            """
            SELECT id, real_name FROM characters WHERE real_name = ?
        """,
            (name,),
        )
        row = self.cursor.fetchone()
        if row:
            return row[0], row[1], None
        return None

    def get_or_create_alias(self, name: str) -> str:
        self.cursor.execute("SELECT id FROM aliases WHERE alias = ?", (name,))
        result = self.cursor.fetchone()
        if result:
            return result[0]
        else:
            new_id = self.generate_uuid()
            self.cursor.execute(
                """
                INSERT INTO aliases (id, alias) VALUES (?, ?)
            """,
                (new_id, name),
            )
            self.conn.commit()
            return new_id

    def is_shared_alias(self, alias_id: str) -> bool:
        self.cursor.execute(
            "SELECT shared_alias FROM aliases WHERE id = ?", (alias_id,)
        )
        return self.cursor.fetchone()[0]

    def resolve_character_id(self, alias_id: str) -> Optional[str]:
        self.cursor.execute(
            """
            SELECT character_id
            FROM character_alias_links
            WHERE alias_id = ?
            """,
            (alias_id,),
        )
        link_row = self.cursor.fetchone()
        character_id = link_row[0] if link_row else None
        return character_id

    def insert_comic_character(self, alias_id: str, character_id: str, certainity: str):
        self.cursor.execute(
            """
            INSERT OR IGNORE INTO comic_characters
                (comic_id, alias_id, character_id, certainity)
            VALUES (?, ?, ?, ?)""",
            (self.comic_id, alias_id, character_id, certainity),
        )

    def db_into_characters(self):
        for character in self.clean_info["characters"]:
            alias_id = self.get_or_create_alias(character)

            shared = self.is_shared_alias(alias_id)

            if shared:
                character_id = None
                certainity = "low"
            else:
                character_id = self.resolve_character_id(alias_id)
                certainity = "high"

            self.insert_comic_character(alias_id, character_id, certainity)

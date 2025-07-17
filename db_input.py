import sqlite3
from typing import Optional

from file_utils import generate_uuid, normalise_publisher_name
from helper_classes import ComicInfo


class MetadataInputting:
    def __init__(self, comicinfo: ComicInfo) -> None:
        self.clean_info = comicinfo
        self.clean_dict = comicinfo.model_dump()
        self.comic_id = comicinfo.primary_key

    def open_connection(self):
        self.conn = sqlite3.connect("comics.db")
        self.cursor = self.conn.cursor()

    def db_into_main_db_table(self):
        self.cursor.execute(
            """
            INSERT INTO comics (id, title, series, volume_id, publisher_id,
            release_date, description, type_id)
            VALUES (:primary_key, :title, :series, :volume_num, :publisher_id, :date,
            :description, :collection_type)
            """,
            self.clean_dict,
        )
        self.conn.commit()

    # =====================
    # Character Insertion
    # =====================

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
            new_id = generate_uuid()
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
        return None

    # ==================
    # Teams Insertion
    # ==================

    def insert_new_teams(self) -> list[tuple[str, int]]:
        teams_ids = []
        if self.clean_info.teams is None:
            raise ValueError("teams cannot be None")
        for team in self.clean_info.teams:
            self.cursor.execute(
                "INSERT OR IGNORE INTO teams (name) VALUES (?)", (team,)
            )
            self.cursor.execute("SELECT id FROM teams WHERE name = ?", (team,))
            row = self.cursor.fetchone()
            if row:
                teams_ids.append((team, row[0]))
        return teams_ids

    def insert_into_comic_teams(self, teams: list[tuple[str, int]]):
        for team in teams:
            self.cursor.execute(
                """
                INSERT INTO comic_teams
                (comic_id, team_id)
                VALUES
                (?, ?)
                """,
                (
                    self.comic_id,
                    team[1],
                ),
            )

    # ====================
    # Creator Insertion
    # ====================

    def insert_new_creators(self) -> list[tuple[str, int]]:
        creators_ids = []
        if self.clean_info.creators is not None:
            for entry in self.clean_info.creators:
                name, _ = entry
                self.cursor.execute(
                    "INSERT OR IGNORE INTO creators (real_name) VALUES (?)", (name,)
                )

                self.cursor.execute(
                    "SELECT id from creators WHERE real_name = ?", (name,)
                )
                row = self.cursor.fetchone()
                if row:
                    creators_ids.append((name, row[0]))
        return creators_ids

    def get_role_ids(self) -> dict[str, int]:
        self.cursor.execute("SELECT id, role_name FROM roles")
        roles = self.cursor.fetchall()
        return {role_name: role_id for role_id, role_name in roles}

    def insert_into_comic_creators(self, creators: list[tuple[str, int]]):
        roles = self.get_role_ids()
        creator_role_pairs = self.clean_info.creators
        creator_role_id_tuples: list[tuple[str, str, int]] = []
        if creator_role_pairs is not None:
            for index, info in enumerate(creators):
                creator_role_id_tuples.append(creator_role_pairs[index] + (info[1],))

        for entry in creator_role_id_tuples:
            _, role, id = entry
            if role in roles.keys():
                role_id = roles[role]
            else:
                role_id = 0
            self.cursor.execute(
                """
                INSERT INTO comic_creators
                (comic_id, creator_id, role_id)
                VALUES
                (?, ?, ?)
                """,
                (self.comic_id, id, role_id),
            )


def insert_new_publisher(publisher_name: str) -> None:
    normalised_name = normalise_publisher_name(publisher_name)
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO publishers (name, normalised_name) VALUES (?, ?)",
        (
            publisher_name,
            normalised_name,
        ),
    )

    conn.commit()
    conn.close()

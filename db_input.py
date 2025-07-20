import sqlite3
from typing import Optional

from file_utils import normalise_publisher_name
from helper_classes import ComicInfo

SHARED_ALIASES = [
    "Robin",
    "Green Lantern",
    "Flash",
    "Captain America",
    "Batgirl",
    "Spider-Man",
    "Ant-Man",
    "Hawkeye",
    "Blue Beetle",
    "Wolverine",
    "Thor",
    "Iron Fist",
    "Hulk",
    "Phoenix",
    "Captain Marvel",
    "Superboy",
    "Black Panther",
    "Venom",
    "Spider-Woman",
    "Ms. Marvel",
    "Superman",
    "Batman",
    "Iron Man",
    "Batwoman",
    "Green Arrow",
    "Atom",
    "Starman",
]


class MetadataInputting:
    def __init__(self, comicinfo: ComicInfo) -> None:
        self.clean_info = comicinfo
        self.clean_dict = comicinfo.model_dump()
        self.comic_id = comicinfo.primary_key
        self.conn = sqlite3.connect("comics.db")
        self.cursor = self.conn.cursor()

    def dict_into_main_db_table(self) -> None:
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

    @staticmethod
    def find_identity(character: str) -> Optional[tuple[str, int]]:
        # TODO: Disambiguation logic goes here.
        return None  # Unknown identity

    def insert_or_find_character(self) -> list[tuple[str, int]]:
        character_ids = []
        if self.clean_info.characters is None:
            raise ValueError("characters cannot be empty")
        for character in self.clean_info.characters:
            identity_info = self.find_identity(character)
            self.cursor.execute(
                "INSERT OR IGNORE INTO characters (name) VALUES (?)", (character,)
            )
            self.cursor.execute(
                "SELECT id FROM characters WHERE name = ?", (character,)
            )
            row = self.cursor.fetchone()
            if row:
                character_ids.append((character, row[0], identity_info))
        self.conn.commit()
        return character_ids

    def insert_into_comic_characters(
        self, characters: list[tuple[str, int, Optional[str]]]
    ) -> None:
        for character in characters:
            _, character_id, identity_info = character
            identity_id = identity_info[1] if identity_info else None
            self.cursor.execute(
                """
                INSERT INTO comic_characters
                (comic_id, character_id, identity_id)
                VALUES
                (?, ?, ?)
                """,
                (
                    self.comic_id,
                    character_id,
                    identity_id,
                ),
            )
        self.conn.commit()

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
        self.conn.commit()
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
        self.conn.commit()

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
        self.conn.commit()
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
        self.conn.commit()

    # ==============
    # Run Function
    # ==============

    def run(self):
        self.dict_into_main_db_table()
        character_info = self.insert_or_find_character()
        self.insert_into_comic_characters(character_info)
        team_info = self.insert_new_teams()
        self.insert_into_comic_teams(team_info)
        creator_info = self.insert_new_creators()
        self.insert_into_comic_creators(creator_info)
        self.conn.commit()

    def insert_filepath(self, filepath):
        print(f"[DEBUG] Updating comic ID {self.comic_id} with path {filepath}")
        self.cursor.execute(
            """
            UPDATE comics
            SET file_path = ?
            WHERE id = ?
            """,
            (filepath, self.comic_id),
        )
        print("[DEBUG] SQL executed")
        print(f"[DEBUG] Rows updated: {self.cursor.rowcount}")
        self.conn.commit()


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

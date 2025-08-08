import os
import sqlite3
from collections import defaultdict

from helper_classes import GUIComicInfo, MetadataInfo


class RepoWorker:
    def __init__(self, cover_dir: str):
        self.cover_folder = cover_dir

    def __enter__(self):
        self.conn = sqlite3.connect("comics.db")
        self.cursor = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.commit()
        self.conn.close()
        return

    def create_basemodel(self, ids: list[str]) -> list[GUIComicInfo]:
        comic_info = []
        for id in ids:
            self.cursor.execute(
                """
                SELECT series, title, file_path
                FROM comics
                WHERE id = ?
                """,
                (id,),
            )
            row = self.cursor.fetchone()
            if not row:
                continue

            series, title, filepath = row

            cover_path = os.path.join(self.cover_folder, f"{id}_b.jpg")

            basemodel = GUIComicInfo(
                primary_id=id,
                title=f"{series}: {title}",
                filepath=filepath,
                cover_path=cover_path,
            )
            comic_info.append(basemodel)

        return comic_info

    def run(self) -> tuple[list[GUIComicInfo], list[GUIComicInfo]]:
        self.cursor.execute(
            """
            SELECT comic_id
            FROM reading_progress
            WHERE is_finished = 0
            ORDER BY last_read DESC
            """
        )
        rows_c = self.cursor.fetchmany(8)
        continue_ids = []
        if rows_c:
            for row in rows_c:
                continue_ids.append(row[0])

        self.cursor.execute(
            """
            SELECT rp.comic_id
            FROM reading_progress rp
            LEFT JOIN reviews r ON rp.comic_id = r.comic_id
            WHERE rp.is_finished = 1 AND (r.comic_id IS NULL OR r.review IS NULL)
            """
        )
        rows_r = self.cursor.fetchmany(8)
        review_ids = []
        if rows_r:
            for row in rows_r:
                review_ids.append(row[0])

        continue_info = self.create_basemodel(continue_ids)
        review_info = self.create_basemodel(review_ids)

        return continue_info, review_info

    def get_recent_page(self, primary_key: str) -> None | int:
        self.cursor.execute(
            "SELECT last_page_read FROM reading_progress WHERE comic_id = ?",
            (primary_key,),
        )
        row = self.cursor.fetchone()
        return row[0] if row else None

    def save_last_page(self, primary_key: str, last_page: int) -> None:
        if self.get_recent_page(primary_key) is not None:
            self.cursor.execute(
                "UPDATE reading_progress SET last_page_read = ? WHERE comic_id = ?",
                (last_page, primary_key),
            )
        else:
            self.cursor.execute(
                """
                INSERT INTO reading_progress (comic_id, last_page_read, is_finished)
                VALUES (?, ?, ?)
                """,
                (primary_key, last_page, 0),
            )

    def mark_as_finished(self, primary_id: str, last_page: int) -> None:
        if self.get_recent_page(primary_id) is not None:
            self.cursor.execute(
                """
                UPDATE reading_progress
                SET (last_page_read, is_finished) = (?, ?)
                WHERE comic_id = ?
                """,
                (
                    last_page,
                    1,
                    primary_id,
                ),
            )
        else:
            self.cursor.execute(
                """
                INSERT INTO reading_progress (comic_id, last_page_read, is_finished)
                VALUES (?, ?, ?)
                """,
                (primary_id, last_page, 1),
            )

    def get_folder_info(self, pub_int: int) -> list[GUIComicInfo]:
        info = []
        self.cursor.execute(
            """SELECT id, title, series, file_path
            FROM comics
            WHERE publisher_id = ?
            ORDER BY volume_id ASC
            """,
            (pub_int,),
        )
        rows = self.cursor.fetchall()
        for row in rows:
            gui_info = GUIComicInfo(
                primary_id=row[0],
                title=f"{row[1]}: {row[2]}",
                filepath=row[3],
                cover_path=f"{self.cover_folder}//{row[0]}_b.jpg",
            )
            info.append(gui_info)
        return info

    def get_complete_metadata(self, primary_id: str) -> MetadataInfo:
        role_info = {
            1: "Writer",
            2: "Penciller",
            3: "Cover Artist",
            4: "Inker",
            5: "Editor",
            6: "Colourist",
            7: "Letterer",
        }

        self.cursor.execute("SELECT * FROM comics WHERE id = ?", (primary_id,))
        comic_info = self.cursor.fetchone()
        self.cursor.execute(
            "SELECT character_id FROM comic_characters WHERE comic_id = ? ",
            (primary_id,),
        )
        character_ids = [row[0] for row in self.cursor.fetchall()]
        self.cursor.execute(
            "SELECT creator_id, role_id FROM comic_creators where comic_id = ?",
            (primary_id,),
        )
        creator_id_info = [(row[0], row[1]) for row in self.cursor.fetchall()]
        self.cursor.execute(
            "SELECT team_id FROM comic_teams WHERE comic_id = ?", (primary_id,)
        )
        team_id_info = [row[0] for row in self.cursor.fetchall()]
        self.cursor.execute("SELECT * FROM reviews WHERE comic_id = ?", (primary_id,))
        review_info = [
            (row[1], row[2], row[3], row[4]) for row in self.cursor.fetchall()
        ]

        title = comic_info[1]
        series = comic_info[2]
        volume_num = comic_info[3]
        publisher_num = comic_info[4]
        release_date = comic_info[5]
        desc = comic_info[7]
        characters = []
        for i in character_ids:
            self.cursor.execute("SELECT name FROM characters WHERE id = ?", (i,))
            characters.append(self.cursor.fetchone()[0])
        role_to_creators = defaultdict(list)
        for j in creator_id_info:
            self.cursor.execute("SELECT real_name FROM creators where id = ?", (j[0],))
            name = self.cursor.fetchone()[0]
            role_name = role_info.get(j[1])
            role_to_creators[role_name].append(name)
            creators_by_role = list(role_to_creators.items())
        teams = []
        for k in team_id_info:
            self.cursor.execute("SELECT name FROM teams WHERE id = ?", (k,))
            team = self.cursor.fetchone()[0]
            teams.append(team)
        if review_info:
            rating = review_info[0][1]
            reviews = [(r[2], r[3], r[0]) for r in review_info]
        else:
            rating = 0
            reviews = []
        self.cursor.execute(
            "SELECT name FROM publishers where id = ?", (publisher_num,)
        )
        publiser_name = self.cursor.fetchone()[0]

        return MetadataInfo(
            primary_id=primary_id,
            name=f"{title}: {series}",
            volume_num=volume_num,
            publisher=publiser_name,
            date=release_date,
            description=desc,
            creators=creators_by_role,
            characters=characters,
            teams=teams,
            rating=rating,
            reviews=reviews,
        )

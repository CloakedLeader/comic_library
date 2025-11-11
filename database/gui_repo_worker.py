import os
import sqlite3
from collections import defaultdict
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path

from classes.helper_classes import GUIComicInfo, MetadataInfo


load_dotenv()
ROOT_DIR = Path(os.getenv("ROOT_DIR"))

class RepoWorker:
    def __init__(self):
        self.cover_folder = str(ROOT_DIR / ".covers")

    def __enter__(self):
        self.conn = sqlite3.connect("comics.db")
        self.cursor = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.commit()
        self.conn.close()
        return

    def create_basemodel(self, ids: list[str]) -> list[GUIComicInfo]:
        """
        Creates a GUIComicInfo class instance for a comic, given its id.

        Parameters:
        ids: A list of uuid4's to create basemodels for. 

        Output:
        Returns a list, in the same order as the input, of GUIComicInfo basemodels.

        This goes through the different tables in the database and extracts information the frontend
        requires. Formats the filepath so it is absolute and then packages all the info into the required
        basemodel. Returns a list in the same order as the input.
        """
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

            series, title, relative_filepath = row
            relative_filepath = Path(relative_filepath)

            cover_path = os.path.join(self.cover_folder, f"{id}_b.jpg")

            basemodel = GUIComicInfo(
                primary_id=id,
                title=f"{series}: {title}",
                filepath=str(ROOT_DIR / relative_filepath),
                cover_path=cover_path,
            )
            comic_info.append(basemodel)

        return comic_info

    def run(self) -> tuple[list[GUIComicInfo], list[float], list[GUIComicInfo]]:
        """
        Goes through the database and finds comics that are partially read, or require reviewing.

        Parameters:
        None

        Outputs:
        A tuple consisting of three lists. The elements of the tuple are:
            1) A list of GUIComicInfo basemodels for comics which are partially read.
            2) A list of the percentage of pages read for each comic in the previous list.
            3) A list of GUIComicInfo basemodels for comics which are finished and need a written review.
        
        Goes through the relevant database tables and find comics that fulfill the requirements of not yet finished,
        or finished but without a written review.
        """
        self.cursor.execute(
            """
            SELECT comic_id, last_page_read
            FROM reading_progress
            WHERE is_finished = 0
            ORDER BY last_read DESC
            """
        )
        rows_c = self.cursor.fetchmany(8)
        continue_ids = []
        progresses = []

        if rows_c:
            for row in rows_c:
                continue_ids.append(row[0])
                last_page = row[1]
                self.cursor.execute(
                    """
                    SELECT page_count
                    FROM comics
                    WHERE id = ?
                    """,
                    (row[0],),
                )
                num_result = self.cursor.fetchone()
                if num_result:
                    total_pages = num_result[0]
                    progresses.append(int(last_page) / int(total_pages))
                else:
                    progresses.append(0.0)

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

        return continue_info, progresses, review_info

    def get_recent_page(self, primary_key: str) -> None | int:
        """
        Gets the last read page from the database, might not be the actual last read page.

        Parameters:
        primary_key: A string that represents the uuid4 for the specific comic.

        Outputs:
        The number of the last read page or None if the comic is not in the reading_progress table.
        """
        self.cursor.execute(
            "SELECT last_page_read FROM reading_progress WHERE comic_id = ?",
            (primary_key,),
        )
        row = self.cursor.fetchone()
        return row[0] if row else None

    def save_last_page(self, primary_key: str, last_page: int) -> None:
        """
        Triggered by the frontend layer, this saves the page number to the database.

        Parameters:
        primary_key: A string that represents the uuid4 for the specific comic.
        last_page: An integer which represents the last read page to be saved,
            will overwrite previous saved page.
        
        If the comic is not in the reading_progress table it adds it and saves the page,
        else it just overwrites what was in the last_page field.
        """
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

    def mark_as_finished(self, primary_key: str, last_page: int) -> None:
        """
        Changes the status of a comic from not finished to finished.

        Parameters:
        primary_key: A string that represents the uuid4 for the specific comic.
        last_page: An integer which represents the last read page.

        Checks if the comic already has an entry in the reading_progress table, if it does change
        its read state from 0 to 1. Else, create the entry in the table with read state equal to 1.
        """
        # TODO: Add verification this actually the last page by looking at comics table.
        if self.get_recent_page(primary_key) is not None:
            self.cursor.execute(
                """
                UPDATE reading_progress
                SET (last_page_read, is_finished) = (?, ?)
                WHERE comic_id = ?
                """,
                (
                    last_page,
                    1,
                    primary_key,
                ),
            )
        else:
            self.cursor.execute(
                """
                INSERT INTO reading_progress (comic_id, last_page_read, is_finished)
                VALUES (?, ?, ?)
                """,
                (primary_key, last_page, 1),
            )

    def get_folder_info(self, pub_int: int) -> list[GUIComicInfo]:
        """
        Gets a list of all comics within a folder and returns a list of GUIComicInfo basemodels.

        Parameters:
        pub_int: An integer which corresponds to a row in the publisher table and is unique.

        Outputs:
        A list of GUIComicInfo basemodels which belong to the folder of the publisher.
        
        Finds all comics corresponding to the respective publisher and compiles their
        information into GUIComicInfo basemodels.
        """
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
                filepath=str(ROOT_DIR / Path(row[3])),
                cover_path=f"{self.cover_folder}//{row[0]}_b.jpg",
            )
            info.append(gui_info)
        return info

    def input_review_column(self, review_text: str, primary_key: str) -> None:
        self.cursor.execute(
            "SELECT iteration, review FROM reviews"
            "WHERE comic_id = ? ORDER BY iteration DESC",
            (primary_key,),
        )
        query_result = self.cursor.fetchone()
        if query_result:
            highest_iteration = query_result[0]
        else:
            highest_iteration = 1

        review = query_result[1]

        if review == review_text:
            return None
        else:
            self.cursor.execute(
                """INSERT INTO reviews
                (comic_id, iteration, review)
                VALUES
                (?, ?, ?)
                """,
                (primary_key, highest_iteration + 1, review_text),
            )
            return None

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
        # iteration, rating, review_text, date

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
            reviews = [(r[2] or "", r[3], r[0]) for r in review_info]
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

    def create_collection(self, title: str):
        self.cursor.execute("INSERT INTO collections (name) VALUES (?)", (title,))

    def get_collections(self) -> tuple[list[str], list[int]]:
        self.cursor.execute("SELECT name, id from collections")
        results = self.cursor.fetchall()
        names = []
        ids = []
        for result in results:
            names.append(result[0])
            ids.append(result[1])

        return (names, ids)

    def add_to_collection(self, collection_id, comic_id):
        self.cursor.execute(
            """
            INSERT OR IGNORE INTO collections_contents
            (collection_id, comic_id)
            VALUES (?, ?)
            """,
            (collection_id, comic_id),
        )

    def get_collection_contents(self, collection_id: int) -> list[str] | None:
        self.cursor.execute(
            "SELECT comic_id FROM collections_contents WHERE collection_id = ?",
            (collection_id,))
        result = self.cursor.fetchall()
        if result:
            return [r[0] for r in result]
        else:
            return None
        
    def create_reading_order(self, title: str, desc: Optional[str]) -> int:
        now = datetime.now()
        if desc is None:
            self.cursor.execute(
                "INSERT INTO reading_orders (name, created) VALUES (?, ?)",
                (title, now,))
        else:
            self.cursor.execute(
                "INSERT INTO reading_orders (name, description, created) VALUES (?, ?, ?)",
                (title, desc, now,))
        return self.cursor.lastrowid
        

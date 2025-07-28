import sqlite3
from helper_classes import GUIComicInfo
import os


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
                (id,)
            )
            row = self.cursor.fetchone()
            if not row:
                continue

            series, title, filepath = row

            cover_path = os.path.join(self.cover_folder, f"{id}_b.jpg")

            basemodel = GUIComicInfo(primary_id=id,
                                     title=f"{series}: {title}",
                                     filepath=filepath,
                                     cover_path=cover_path
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
            (primary_key,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def save_last_page(self, primary_key: str, last_page: int) -> None:
        if self.get_recent_page(primary_key):
            self.cursor.execute(
                "UPDATE reading_progress SET last_page_read = ? WHERE comic_id = ?",
                (last_page, primary_key)
            )
        else:
            self.cursor.execute(
                """
                INSERT INTO reading_progress (comic_id, last_page_read, is_finished)
                VALUES (?, ?, ?)
                """,
                (primary_key, last_page, 0)
            )

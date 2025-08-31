import os
import sqlite3
from pathlib import Path
from typing import Optional

from sqlmodel import Field, Session, SQLModel, select


class Comics(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True)
    file_path: str
    publisher_id: int


def get_file_to_id_mapping(session: Session, pub_id: Optional[int] = None):
    query = select(Comics.id, Comics.file_path)

    if pub_id is not None:
        query = query.where(Comics.publisher_id == pub_id)

    result = session.exec(query).all()
    return {str(Path(filepath).name): comic_id for comic_id, filepath in result}


def build_tree(folder_name: str, file_to_id: dict):
    items = []
    for entry in sorted(os.listdir(f"D:/adams-comics/{folder_name}")):
        full_path = os.path.join(folder_name, entry)
        if os.path.isdir(full_path):
            items.append(
                {
                    "name": entry,
                    "type": "folder",
                    "children": build_tree(full_path, file_to_id),
                }
            )
        else:
            comic_id = file_to_id.get(entry)
            items.append(
                {
                    "name": entry,
                    "type": "file",
                    "id": comic_id,
                }
            )
    return items


def get_base_folders(path: str):
    items = []
    for entry in sorted(os.listdir(path)):
        full_path = os.path.join(path, entry)
        if entry[0] != "." and os.path.isdir(full_path):
            items.append({"name": entry, "type": "folder", "pub_id": entry[0]})

    return items


def get_filepath(comic_id: str) -> str:
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT filepath
        FROM comics
        WHERE id = ?
        """,
        (comic_id,),
    )
    row = cursor.fetchone()
    if row:
        filepath = row[0]
    return filepath

import sqlite3

from extract_meta_xml import MetadataExtraction
from helper_classes import ComicInfo
from metadata_cleaning import MetadataProcessing


def get_metadata(comic_id: str) -> ComicInfo:
    filepath = get_filepath(comic_id)
    base_info = ComicInfo(primary_key=comic_id, filepath=filepath)
    with MetadataExtraction(base_info) as extractor:
        comic_info = extractor.run()
    with MetadataProcessing(comic_info) as cleaner:
        clean_info = cleaner.run()

    return clean_info


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

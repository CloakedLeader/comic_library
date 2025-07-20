import sqlite3

conn = sqlite3.connect("comics.db")
cursor = conn.cursor()


# cursor.execute("DELETE FROM reading_progress")
cursor.execute(
    """
    INSERT INTO reading_progress
    (comic_id, last_page_read, is_finished)
    VALUES
    (?, ?, ?)
    """,
    ("a8a55710-d1b2-45ac-8bd6-e664696e9f1a", 0, 0))

conn.commit()
conn.close()

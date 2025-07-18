import sqlite3

conn = sqlite3.connect("comics.db")
cursor = conn.cursor()

cursor.execute(
    """
    UPDATE comic_creators
    SET role_id = (?)
    WHERE creator_id = (?)
    """, (7, 8,)
)

conn.commit()
conn.close()

import sqlite3

conn = sqlite3.connect("comics.db")
cursor = conn.cursor()


cursor.execute("DELETE FROM comics")
# cursor.execute(
#     """
#     INSERT INTO reading_progress
#     (comic_id, last_page_read, is_finished)
#     VALUES
#     (?, ?, ?)
#     """,
#     ("89dbfec9-3ce3-4b4a-9063-725913adddea", 0, 0))

conn.commit()
conn.close()

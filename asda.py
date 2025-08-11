import sqlite3

conn = sqlite3.connect("comics.db")
cursor = conn.cursor()

cursor.execute("DROP TABLE comics_fts5")
cursor.execute(
    """
    CREATE VIRTUAL TABLE comics_fts5 USING fts5(
        comic_id UNINDEXED,
        series,
        title,
        creators,
        characters,
        teams,
    )
    """
)

conn.commit()
conn.close()

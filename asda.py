import sqlite3

conn = sqlite3.connect("comics.db")
cursor = conn.cursor()

# cursor.execute("DROP TABLe comics_fts5")

# cursor.execute(
#     """
#     CREATE VIRTUAL TABLE comics_fts5 USING fts5(
#     id UNINDEXED,
#     title
#     )
#     """
# )

cursor.execute(
    """
    INSERT INTO comics_fts5(id, title)
    SELECT id, title FROM comics
    """
)

conn.commit()

from sqlite3 import connect

connection = connect("comics.db")
cursor = connection.cursor()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS collections(
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    subfolder_id INTEGER,
    FOREIGN KEY (subfolder_id) REFERENCES collections(id)
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS collections_contents(
    collection_id INTEGER NOT NULL,
    comic_id TEXT NOT NULL,
    PRIMARY KEY (collection_id, comic_id),
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
    )
    """
)

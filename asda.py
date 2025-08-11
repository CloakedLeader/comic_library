import sqlite3

conn = sqlite3.connect("comics.db")
cursor = conn.cursor()

cursor.execute("DROP TABLE reviews")
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS reviews (
    comic_id TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    rating INTEGER CHECK (rating BETWEEN 1 AND 10),
    review TEXT,
    date_reviewed TEXT DEFAULT CURRENT_DATE,
    PRIMARY KEY (comic_id, iteration),
    FOREIGN KEY (comic_id) REFERENCES comics(id)
    )
    """
)

conn.commit()
conn.close()

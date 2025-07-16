import sqlite3

conn = sqlite3.connect("comics.db")
cursor = conn.cursor()

cursor.execute(
    """
                CREATE TABLE IF NOT EXISTS comics (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    series TEXT,
                    volume_id INTEGER,
                    publisher_id INTEGER,
                    release_date TEXT,
                    file_path TEXT,
                    description TEXT,
                    type_id INTEGER,
                    FOREIGN KEY (type_id) REFERENCES comic_types(id),
                    FOREIGN KEY (publisher_id) REFERENCES publishers(id),
                    FOREIGN KEY (series) REFERENCES series(id)
                )
"""
)

cursor.execute(
    """
                CREATE TABLE IF NOT EXISTS publishers (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
"""
)

cursor.execute(
    """
                CREATE TABLE IF NOT EXISTS creators (
                    id TEXT PRIMARY KEY,
                    real_name TEXT NOT NULL UNIQUE
                )
"""
)

cursor.execute(
    """
                CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL UNIQUE
                )
"""
)

cursor.execute(
    "INSERT INTO roles (role_name) VALUES ('Writer'), ('Penciller'), ('CoverArtist'),"
    "('Inker'), ('Editor'), ('Colorist')"
)

cursor.execute(
    """
                CREATE TABLE IF NOT EXISTS comic_creators (
                    comic_id TEXT NOT NULL,
                    creator_id TEXT NOT NULL,
                    role_id INTEGER NOT NULL,
                    PRIMARY KEY (comic_id, creator_id, role_id),
                    FOREIGN KEY (comic_id) REFERENCES comics(id),
                    FOREIGN KEY (creator_id) REFERENCES creators(id),
                    FOREIGN KEY (role_id) REFERENCES roles(id)
                )
"""
)

cursor.execute(
    """
                CREATE TABLE IF NOT EXISTS characters (
                    id  TEXT PRIMARY KEY,
                    real_name TEXT NOT NULL UNIQUE
                )
"""
)

cursor.execute(
    """
                CREATE TABLE aliases (
                id TEXT PRIMARY KEY,
                alias TEXT NOT NULL UNIQUE
                )

"""
)
SHARED_ALIASES = [
    "Robin",
    "Green Lantern",
    "Flash",
    "Captain America",
    "Batgirl",
    "Spider-Man",
    "Ant-Man",
    "Hawkeye",
    "Blue Beetle",
    "Wolverine",
    "Thor",
    "Iron Fist",
    "Hulk",
    "Phoenix",
    "Captain Marvel",
    "Superboy",
    "Black Panther",
    "Venom",
    "Spider-Woman",
    "Ms. Marvel",
    "Superman",
    "Batman",
    "Iron Man",
    "Batwoman",
    "Green Arrow",
    "Atom",
    "Starman",
]
for alias in SHARED_ALIASES:
    cursor.execute(
        """
        UPDATE aliases SET shared_alias = 1 WHERE alias = ?
        """,
        (alias,),
    )

cursor.execute(
    """
                CREATE TABLE character_alias_links (
                character_id TEXT NOT NULL,
                alias_id TEXT NOT NULL,
                PRIMARY KEY (character_id, alias_id),
                FOREIGN KEY (character_id) REFERENCES characters(id),
                FOREIGN KEY (alias_id) REFERENCES aliases(id)
                )
"""
)

cursor.execute(
    """
                CREATE TABLE comic_characters (
                comic_id TEXT NOT NULL,
                alias_id TEXT NOT NULL,
                character_id TEXT,
                certainity TEXT,
                PRIMARY KEY (comic_id, alias_id),
                FOREIGN KEY (comic_id) REFERENCES comics(id),
                FOREIGN KEY (alias_id) REFERENCES aliases(id),
                FOREIGN KEY (character_id) REFERENCES characters(id)
                )
"""
)

cursor.execute(
    """
                CREATE TABLE IF NOT EXISTS comic_types (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE
                )
"""
)

cursor.execute(
    """
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY,
                    comic_id TEXT NOT NULL,
                    rating INTEGER CHECK (rating BETWEEN 1 AND 10),
                    review TEXT,
                    date_reviewed TEXT DEFAULT CURRENT_DATE,
                    FOREIGN KEY (comic_id) REFERENCES comics(id)
                        )
               """
)

conn.commit()
conn.close()

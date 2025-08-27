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
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    normalised_name TEXT NOT NULL
                )
"""
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS creators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    creator_id INTEGER NOT NULL,
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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
    )
    """
)

cursor.execute(
    """
    CREATE TABLE identities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    real_name TEXT NOT NULL UNIQUE
    )
    """
)

cursor.execute(
    """
    CREATE TABLE character_identity_links (
    character_id INTEGER NOT NULL,
    identity_id INTEGER NOT NULL,
    PRIMARY KEY (character_id, identity_id),
    FOREIGN KEY (character_id) REFERENCES characters(id),
    FOREIGN KEY (identity_id) REFERENCES identities(id)
    )
    """
)

cursor.execute(
    """
    CREATE TABLE comic_characters (
    comic_id TEXT NOT NULL,
    character_id INTEGER NOT NULL,
    identity_id INTEGER,
    PRIMARY KEY (comic_id, character_id),
    FOREIGN KEY (comic_id) REFERENCES comics(id),
    FOREIGN KEY (identity_id) REFERENCES identity(id),
    FOREIGN KEY (character_id) REFERENCES characters(id)
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS comic_teams (
    comic_id TEXT NOT NULL,
    team_id INTEGER NOT NULL,
    PRIMARY KEY (comic_id, team_id),
    FOREIGN KEY (comic_id) REFERENCES comics(id),
    FOREIGN KEY (team_id) REFERENCES teams(id)
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

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS reading_progress (
    comic_id TEXT PRIMARY KEY,
    last_page_read INTEGER DEFAULT 0,
    is_finished BOOLEAN DEFAULT 0,
    last_read INTEGER DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (comic_id) REFERENCES comics(id)
    )
    """
)

conn.commit()
conn.close()

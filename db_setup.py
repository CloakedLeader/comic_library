import sqlite3
conn = sqlite3.connect('comics.db')
cursor = conn.cursor()

cursor.execute('DROP TABLE comics')

cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS comics (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    series TEXT,
                    volume_id INTEGER,
                    publisher_id INTEGER,
                    release_date TEXT,
                    file_path TEXT,
                    front_cover_path TEXT,
                    cover_image_path TEXT,
                    description TEXT,
                    type_id INTEGER,
                    FOREIGN KEY (type_id) REFERENCES comic_types(id),
                    FOREIGN KEY (publisher_id) REFERENCES publishers(id),
                    FOREIGN KEY (series) REFERENCES series(id)
                )
''')

cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS publishers (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL
                )
''')

cursor.execute(''' 
                CREATE TABLE IF NOT EXISTS creators (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE
                )
''')

cursor.execute('''
                CREATE TABLE IF NOT EXISTS comic_creators (
                    comic_id INTEGER,
                    creator_id INTEGER,
                    role TEXT NOT NULL,
                    FOREIGN KEY (comic_id) REFERENCES comics(id),
                    FOREIGN KEY (creator_id) REFERENCES creators(id),
                    PRIMARY KEY (comic_id, creator_id, role)
                )
''')

cursor.execute('''
                CREATE TABLE IF NOT EXISTS characters (
                    id  PRIMARY KEY, 
                    name TEXT NOT NULL
                )
''')

cursor.execute('''
                CREATE TABLE IF NOT EXISTS comic_types (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE
                )
''')


conn.commit()
conn.close()

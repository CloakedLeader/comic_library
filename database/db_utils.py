import sqlite3


def get_publisher_info() -> list[tuple[int, str, str]]:
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, normalised_name FROM publishers")
    results = cursor.fetchall()
    conn.close()
    return results

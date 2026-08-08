import sqlite3

from my_project.config.config_manager import ConfigManager


def get_publisher_info(config_manager: ConfigManager) -> list[tuple[int, str, str]]:
    conn = sqlite3.connect(str(config_manager.config.database.path))
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, normalised_name FROM publishers")
    results = cursor.fetchall()
    conn.close()
    return results

import sqlite3
from unittest.mock import MagicMock, call, patch

import pytest

from database.db_setup import create_tables, insert_roles


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXPECTED_TABLES = [
    "comics",
    "publishers",
    "creators",
    "roles",
    "comic_creators",
    "characters",
    "identities",
    "character_identity_links",
    "comic_characters",
    "teams",
    "comic_teams",
    "comic_types",
    "reviews",
    "reading_progress",
    "collections",
    "collections_contents",
    "reading_orders",
    "reading_order_items",
    "rss_entries",
]

EXPECTED_ROLES = {"Writer", "Penciller", "CoverArtist", "Inker", "Editor", "Colorist"}


def _in_memory_conn():
    """Return a real SQLite in-memory connection."""
    return sqlite3.connect(":memory:")


# ---------------------------------------------------------------------------
# create_tables()
# ---------------------------------------------------------------------------


class TestCreateTables:
    def test_creates_all_expected_tables(self):
        """All regular tables are created by create_tables()."""
        conn = _in_memory_conn()
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            create_tables()

        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        created = {row[0] for row in cursor.fetchall()}
        for table in EXPECTED_TABLES:
            assert table in created, f"Table '{table}' was not created"

    def test_creates_fts5_virtual_table(self):
        """The comics_fts5 virtual table is created."""
        conn = _in_memory_conn()
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            create_tables()

        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='comics_fts5'"
        )
        assert cursor.fetchone() is not None

    def test_idempotent_when_called_twice(self):
        """create_tables() can be called twice without raising an error (IF NOT EXISTS)."""
        conn = _in_memory_conn()
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            create_tables()
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            create_tables()

        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        created = {row[0] for row in cursor.fetchall()}
        for table in EXPECTED_TABLES:
            assert table in created

    def test_commits_and_closes_connection(self):
        """create_tables() commits and closes the connection."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("database.db_setup.sqlite3.connect", return_value=mock_conn):
            create_tables()

        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_comics_table_schema(self):
        """The comics table has the expected columns."""
        conn = _in_memory_conn()
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            create_tables()

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(comics)")
        columns = {row[1] for row in cursor.fetchall()}
        expected_columns = {
            "id",
            "title",
            "series",
            "volume_id",
            "publisher_id",
            "release_date",
            "file_path",
            "description",
            "type_id",
            "page_count",
        }
        assert expected_columns <= columns

    def test_publishers_table_schema(self):
        """The publishers table has the expected columns."""
        conn = _in_memory_conn()
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            create_tables()

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(publishers)")
        columns = {row[1] for row in cursor.fetchall()}
        assert {"id", "name", "normalised_name"} <= columns

    def test_roles_table_schema(self):
        """The roles table has the expected columns."""
        conn = _in_memory_conn()
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            create_tables()

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(roles)")
        columns = {row[1] for row in cursor.fetchall()}
        assert {"id", "role_name"} <= columns

    def test_reviews_rating_constraint(self):
        """The reviews table enforces a CHECK constraint on rating (1–10)."""
        conn = _in_memory_conn()
        conn.execute("PRAGMA foreign_keys = OFF")
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            create_tables()

        # Valid rating should succeed
        conn.execute(
            "INSERT INTO reviews (comic_id, iteration, rating) VALUES ('c1', 1, 5)"
        )
        conn.commit()

        # Rating out of range should raise
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO reviews (comic_id, iteration, rating) VALUES ('c2', 1, 11)"
            )
            conn.commit()

    def test_reading_progress_defaults(self):
        """reading_progress has default values for last_page_read and is_finished."""
        conn = _in_memory_conn()
        conn.execute("PRAGMA foreign_keys = OFF")
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            create_tables()

        conn.execute("INSERT INTO reading_progress (comic_id) VALUES ('c1')")
        conn.commit()

        cursor = conn.cursor()
        cursor.execute(
            "SELECT last_page_read, is_finished FROM reading_progress WHERE comic_id='c1'"
        )
        row = cursor.fetchone()
        assert row[0] == 0
        assert row[1] == 0

    def test_connects_to_comics_db(self):
        """create_tables() connects to 'comics.db' by default."""
        with patch("database.db_setup.sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = MagicMock()
            mock_connect.return_value = mock_conn
            create_tables()

        mock_connect.assert_called_once_with("comics.db")

    def test_reading_orders_schema(self):
        """reading_orders table has the expected columns including description."""
        conn = _in_memory_conn()
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            create_tables()

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(reading_orders)")
        columns = {row[1] for row in cursor.fetchall()}
        assert {"id", "name", "description", "created"} <= columns

    def test_rss_entries_schema(self):
        """rss_entries table has the expected columns."""
        conn = _in_memory_conn()
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            create_tables()

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(rss_entries)")
        columns = {row[1] for row in cursor.fetchall()}
        assert {"url", "title", "pub_epoch", "summary", "cover_url"} <= columns


# ---------------------------------------------------------------------------
# insert_roles()
# ---------------------------------------------------------------------------


class TestInsertRoles:
    def test_inserts_all_six_roles(self):
        """insert_roles() inserts exactly the six expected roles."""
        conn = _in_memory_conn()
        # Create the roles table first
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            create_tables()

        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            insert_roles()

        cursor = conn.cursor()
        cursor.execute("SELECT role_name FROM roles")
        roles = {row[0] for row in cursor.fetchall()}
        assert roles == EXPECTED_ROLES

    def test_idempotent_on_repeated_calls(self):
        """insert_roles() uses INSERT OR IGNORE — calling it twice leaves only 6 rows."""
        conn = _in_memory_conn()
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            create_tables()

        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            insert_roles()
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            insert_roles()

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM roles")
        count = cursor.fetchone()[0]
        assert count == 6

    def test_commits_and_closes_connection(self):
        """insert_roles() commits and closes the connection."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("database.db_setup.sqlite3.connect", return_value=mock_conn):
            insert_roles()

        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_connects_to_comics_db(self):
        """insert_roles() connects to 'comics.db' by default."""
        with patch("database.db_setup.sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = MagicMock()
            mock_connect.return_value = mock_conn
            insert_roles()

        mock_connect.assert_called_once_with("comics.db")

    def test_role_names_exact_spelling(self):
        """Role names match exact expected strings (case-sensitive)."""
        conn = _in_memory_conn()
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            create_tables()
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            insert_roles()

        cursor = conn.cursor()
        cursor.execute("SELECT role_name FROM roles ORDER BY role_name")
        roles = [row[0] for row in cursor.fetchall()]
        assert "Writer" in roles
        assert "Penciller" in roles
        assert "CoverArtist" in roles
        assert "Inker" in roles
        assert "Editor" in roles
        assert "Colorist" in roles

    def test_does_not_insert_partial_roles_on_duplicate(self):
        """Pre-existing roles are not duplicated — INSERT OR IGNORE semantics."""
        conn = _in_memory_conn()
        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            create_tables()

        # Manually insert one role before calling insert_roles()
        conn.execute("INSERT INTO roles (role_name) VALUES ('Writer')")
        conn.commit()

        with patch("database.db_setup.sqlite3.connect", return_value=conn):
            insert_roles()

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM roles WHERE role_name='Writer'")
        count = cursor.fetchone()[0]
        assert count == 1

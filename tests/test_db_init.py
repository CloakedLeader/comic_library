import os
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

import db_init
from db_init import ensure_db_exists, ensure_env_and_db, startup_checks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_path_class(base_dir: Path):
    """
    Return a drop-in replacement for pathlib.Path that intercepts
    Path(__file__) calls inside db_init so they resolve to *base_dir*.
    All other Path constructions pass through to the real implementation.
    """
    real_path = Path

    class PatchedPath(type(base_dir)):
        def __new__(cls, *args, **kwargs):
            # When db_init calls Path(__file__), __file__ ends with '.py'
            if args and isinstance(args[0], str) and args[0].endswith(".py"):
                # Return a real Path pointing at our temp location so that
                # .resolve().parent gives us base_dir.
                obj = real_path.__new__(real_path, base_dir / "db_init.py")
                return obj
            return real_path.__new__(real_path, *args, **kwargs)

    return PatchedPath


# ---------------------------------------------------------------------------
# ensure_db_exists()
# ---------------------------------------------------------------------------


class TestEnsureDbExists:
    def test_does_nothing_when_db_already_exists(self, tmp_path):
        """ensure_db_exists() leaves an existing file untouched."""
        db_file = tmp_path / "comics.db"
        db_file.write_bytes(b"")
        ensure_db_exists(db_file)
        assert db_file.exists()

    def test_creates_parent_directories_when_missing(self, tmp_path):
        """ensure_db_exists() creates parent dirs for a missing db path."""
        db_file = tmp_path / "nested" / "sub" / "comics.db"
        assert not db_file.parent.exists()
        ensure_db_exists(db_file)
        assert db_file.parent.exists()

    def test_does_not_create_db_file_itself(self, tmp_path):
        """ensure_db_exists() only creates directories, not the db file."""
        db_file = tmp_path / "nested" / "comics.db"
        ensure_db_exists(db_file)
        # Parent dir should exist but the file itself is not created here
        assert db_file.parent.exists()
        assert not db_file.exists()

    def test_accepts_string_path(self, tmp_path):
        """ensure_db_exists() coerces a string argument to Path."""
        db_file = tmp_path / "nested" / "comics.db"
        ensure_db_exists(str(db_file))
        assert db_file.parent.exists()

    def test_existing_parent_no_error(self, tmp_path):
        """ensure_db_exists() does not fail when the parent dir already exists."""
        db_file = tmp_path / "comics.db"
        # tmp_path already exists; should not raise
        ensure_db_exists(db_file)

    def test_deeply_nested_path(self, tmp_path):
        """ensure_db_exists() handles deeply nested missing directories."""
        db_file = tmp_path / "a" / "b" / "c" / "d" / "comics.db"
        ensure_db_exists(db_file)
        assert db_file.parent.exists()


# ---------------------------------------------------------------------------
# ensure_env_and_db()
# ---------------------------------------------------------------------------


class TestEnsureEnvAndDb:
    def test_creates_env_file_when_missing(self, tmp_path, monkeypatch):
        """When .env does not exist, ensure_env_and_db() creates it."""
        monkeypatch.setattr(db_init, "Path", _make_path_class(tmp_path))

        with patch("db_init.ensure_db_exists") as mock_ensure:
            ensure_env_and_db()

        env_file = tmp_path / ".env"
        assert env_file.exists()

    def test_env_file_contains_root_dir_when_created(self, tmp_path, monkeypatch):
        """Newly created .env file contains ROOT_DIR entry."""
        monkeypatch.setattr(db_init, "Path", _make_path_class(tmp_path))

        with patch("db_init.ensure_db_exists"):
            ensure_env_and_db()

        env_content = (tmp_path / ".env").read_text()
        assert "ROOT_DIR=" in env_content

    def test_calls_ensure_db_exists_when_env_missing(self, tmp_path, monkeypatch):
        """When .env is absent, ensure_db_exists() is called with the default path."""
        monkeypatch.setattr(db_init, "Path", _make_path_class(tmp_path))

        with patch("db_init.ensure_db_exists") as mock_ensure:
            ensure_env_and_db()

        mock_ensure.assert_called_once()
        called_path = mock_ensure.call_args[0][0]
        assert str(called_path).endswith("comics.db")

    def test_loads_dotenv_when_env_exists(self, tmp_path, monkeypatch):
        """When .env exists, load_dotenv() is called."""
        env_file = tmp_path / ".env"
        env_file.write_text("ROOT_DIR=/some/path/comics.db\n")

        monkeypatch.setattr(db_init, "Path", _make_path_class(tmp_path))

        with patch("db_init.load_dotenv") as mock_load, \
             patch("db_init.os.getenv", return_value="/some/path/comics.db"), \
             patch("db_init.ensure_db_exists"):
            ensure_env_and_db()

        mock_load.assert_called_once()

    def test_uses_root_dir_from_env_when_set(self, tmp_path, monkeypatch):
        """When ROOT_DIR is set in .env, ensure_db_exists() is called with that path."""
        env_file = tmp_path / ".env"
        db_path = str(tmp_path / "custom" / "comics.db")
        env_file.write_text(f"ROOT_DIR={db_path}\n")

        monkeypatch.setattr(db_init, "Path", _make_path_class(tmp_path))

        with patch("db_init.load_dotenv"), \
             patch("db_init.os.getenv", return_value=db_path), \
             patch("db_init.ensure_db_exists") as mock_ensure:
            ensure_env_and_db()

        mock_ensure.assert_called_once()
        called_path = Path(mock_ensure.call_args[0][0])
        assert str(called_path) == db_path

    def test_env_file_not_created_when_already_exists(self, tmp_path, monkeypatch):
        """ensure_env_and_db() does not overwrite an existing .env file."""
        env_file = tmp_path / ".env"
        original_content = "ROOT_DIR=/existing/path/comics.db\n"
        env_file.write_text(original_content)

        monkeypatch.setattr(db_init, "Path", _make_path_class(tmp_path))

        with patch("db_init.load_dotenv"), \
             patch("db_init.os.getenv", return_value="/existing/path/comics.db"), \
             patch("db_init.ensure_db_exists"):
            ensure_env_and_db()

        assert env_file.read_text() == original_content

    def test_handles_empty_root_dir_env_var(self, tmp_path, monkeypatch):
        """When ROOT_DIR env var is empty/None, ensure_db_exists falls back to default."""
        env_file = tmp_path / ".env"
        env_file.write_text("ROOT_DIR=\n")

        monkeypatch.setattr(db_init, "Path", _make_path_class(tmp_path))

        with patch("db_init.load_dotenv"), \
             patch("db_init.os.getenv", return_value=None), \
             patch("db_init.ensure_db_exists") as mock_ensure:
            # Path(None or "") == Path("") which is not == "", so the else branch runs
            # and ensure_db_exists is called with Path("")
            ensure_env_and_db()

        mock_ensure.assert_called_once()


# ---------------------------------------------------------------------------
# startup_checks()
# ---------------------------------------------------------------------------


class TestStartupChecks:
    def test_calls_ensure_env_and_db(self):
        """startup_checks() calls ensure_env_and_db()."""
        with patch("db_init.ensure_env_and_db") as mock_env, \
             patch("db_init.create_tables"), \
             patch("db_init.insert_roles"):
            startup_checks()

        mock_env.assert_called_once()

    def test_calls_create_tables(self):
        """startup_checks() calls create_tables()."""
        with patch("db_init.ensure_env_and_db"), \
             patch("db_init.create_tables") as mock_tables, \
             patch("db_init.insert_roles"):
            startup_checks()

        mock_tables.assert_called_once()

    def test_calls_insert_roles(self):
        """startup_checks() calls insert_roles()."""
        with patch("db_init.ensure_env_and_db"), \
             patch("db_init.create_tables"), \
             patch("db_init.insert_roles") as mock_roles:
            startup_checks()

        mock_roles.assert_called_once()

    def test_calls_in_correct_order(self):
        """startup_checks() calls functions in order: ensure_env_and_db → create_tables → insert_roles."""
        call_order = []

        with patch("db_init.ensure_env_and_db", side_effect=lambda: call_order.append("env")), \
             patch("db_init.create_tables", side_effect=lambda: call_order.append("tables")), \
             patch("db_init.insert_roles", side_effect=lambda: call_order.append("roles")):
            startup_checks()

        assert call_order == ["env", "tables", "roles"]

    def test_propagates_exception_from_ensure_env_and_db(self):
        """startup_checks() does not swallow exceptions from ensure_env_and_db()."""
        with patch("db_init.ensure_env_and_db", side_effect=RuntimeError("env error")), \
             patch("db_init.create_tables"), \
             patch("db_init.insert_roles"):
            with pytest.raises(RuntimeError, match="env error"):
                startup_checks()

    def test_propagates_exception_from_create_tables(self):
        """startup_checks() does not swallow exceptions from create_tables()."""
        with patch("db_init.ensure_env_and_db"), \
             patch("db_init.create_tables", side_effect=RuntimeError("db error")), \
             patch("db_init.insert_roles"):
            with pytest.raises(RuntimeError, match="db error"):
                startup_checks()
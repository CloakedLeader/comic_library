import os
from pathlib import Path
from dotenv import load_dotenv

from database.db_setup import create_tables, insert_roles

def ensure_env_and_db() -> None:
    base_dir = Path(__file__).resolve().parent
    env_path = base_dir / ".env"

    if not env_path.exists():
        default_db = base_dir / "comics.db"
        env_path.write_text(f"ROOT_DIR={default_db}\n")
        ensure_db_exists(default_db)
        return
    
    load_dotenv(".env")
    db_path = Path(os.getenv("ROOT_DIR") or "")
    if db_path == "":
        default_db = base_dir / "comics.db"
        with env_path.open("a") as f:
            f.write(f"ROOT_DIR={default_db}\n")
        ensure_db_exists(default_db)
        return
    else:
        ensure_db_exists(db_path)
        return
    
def ensure_db_exists(db_path: Path | str) -> None:
    db_path = Path(db_path)
    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)


def startup_checks() -> None:
    ensure_env_and_db()
    create_tables()
    insert_roles()




    



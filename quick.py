from metadata_controller import MetadataController
from main import HomePage
from pathlib import Path
from PySide6.QtWidgets import QApplication
import sys
from qasync import QEventLoop
import asyncio
from dotenv import load_dotenv
import os
import logging
from database.gui_repo_worker import RepoWorker
from file_utils import generate_uuid

logging.basicConfig(
    filename="debug.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


load_dotenv()
API_KEY = os.getenv("API_KEY", "")
root_folder = os.getenv("ROOT_DIR")
ROOT_DIR = Path(root_folder if root_folder is not None else "")
downloads_dir = ROOT_DIR / "0 - Downloads"
qt_app = QApplication(sys.argv)
loop = QEventLoop(qt_app)
asyncio.set_event_loop(loop)
asyncio.get_event_loop().set_debug(False)

home = HomePage()
for path in (ROOT_DIR / "1 - Marvel Comics").rglob("*"):
    if path.is_dir():
        continue
    if path.is_file():
        logging.info(f"Starting to process {path.name}")
        with RepoWorker() as worker:
            if worker.comic_in_db(path):
                continue
        new_id = generate_uuid()
        cont = MetadataController(new_id, path, home)
        cont.process()

import logging
import os
import shutil
import sqlite3
import zipfile
from pathlib import Path
from typing import Optional

from defusedxml import ElementTree as ET
from dotenv import load_dotenv
from PySide6.QtWidgets import QMainWindow

from classes.helper_classes import ComicInfo
from comic_match_logic import ComicMatch, ResultsFilter
from cover_processing import ImageExtraction
from database.db_input import MetadataInputting, insert_new_publisher
from extract_meta_xml import MetadataExtraction
from file_utils import convert_cbz, generate_uuid
from metadata_cleaning import MetadataProcessing, PublisherNotKnown
from search import insert_into_fts5
from tagging_controller import RequestData, extract_and_insert, run_tagging_process

logging.basicConfig(
    filename="debug.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

load_dotenv()
API_KEY = os.getenv("API_KEY", "")
root_folder = os.getenv("ROOT_DIR")
ROOT_DIR = Path(root_folder if root_folder is not None else "")


def get_comicid_from_path(path: Path) -> int:
    """
    Finds the ID of the comic in the database from its filepath.

    Args:
        path: the filepath of the comic archive to be searched against.

    Raises:
        LookupError: if the comic is not found in the database.
    """
    path = Path(path)
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM comics WHERE path = ?", (str(path),))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    else:
        raise LookupError(f"No comic found in database for path: {path}")


# use Amazing Spider-Man Modern Era Epic Collection: Coming Home

# File Naming System: [Series_Name][Start_Year] -
# [Collection_Type] [Volume_Number] ([date in month/year])
# User Visible Title: [Series] [star_year] -
# [collection type] Volume [volume_number]: [Title] [month] [year]

path_to_obs = os.getenv("PATH_TO_WATCH")


class MetadataController:
    def __init__(self, primary_key: str, filepath: Path, display: QMainWindow):
        self.primary_key = primary_key
        self.original_filepath = filepath
        self.display = display
        self.original_filename = filepath.stem
        self.filepath: Path = filepath
        self.filename: str = filepath.stem
        self.comic_info: ComicInfo = ComicInfo(
            primary_key=self.primary_key,
            filepath=self.filepath,
            original_filename=self.original_filename,
        )
        self.page_count: Optional[int] = None

    def reformat(self) -> None:
        temp_filepath = self.original_filepath
        if temp_filepath.suffix == ".cbr":
            temp_filepath = convert_cbz(temp_filepath)
            self.filepath = temp_filepath
        elif temp_filepath.suffix != ".cbz":
            raise ValueError("Wrong filetype.")

    def get_pagecount(self) -> int:
        if self.filepath is None:
            logging.error("Filename must not be None")
            return False
        with zipfile.ZipFile(self.filepath, "r") as archive:
            image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
            image_files = [
                f
                for f in archive.namelist()
                if os.path.splitext(f)[1].lower() in image_exts
            ]
            self.page_count = len(image_files)

        return len(image_files)

    def has_metadata(self) -> bool:
        """
        Checks that the required metadata fields are complete with some info
        e.g. that they are not blank.

        Args:
        required: A list of the fields that must be present.

        Returns:
        True if all required info is present, else False.
        """
        required_fields = [
            "Title",
            "Series",
            "Year",
            "Number",
            "Writer",
            "Penciller",
            "Summary",
        ]
        if self.filepath is None:
            logging.error("Filename must not be None")
            return False
        with zipfile.ZipFile(self.filepath, "r") as archive:
            image_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
            image_files = [
                f
                for f in archive.namelist()
                if os.path.splitext(f)[1].lower() in image_exts
            ]
            self.page_count = len(image_files)
            if "ComicInfo.xml" in archive.namelist():
                with archive.open("ComicInfo.xml") as xml_file:
                    try:
                        tree = ET.parse(xml_file)
                        root = tree.getroot()
                        if root:
                            missing = [
                                tag
                                for tag in required_fields
                                if root.find(tag) is None or root.find(tag) == ""
                            ]

                            if missing:
                                logging.error(f"ComicInfo.xml is missing tags: {missing}")
                                return False
                            else:
                                logging.debug("ComicInfo.xml is valid and complete")
                                return True
                        else:
                            logging.warning("No content in XML")
                            return False

                    except ET.ParseError:
                        logging.warning("ComicInfo.xml is present but not valid xml")
                        return False
            else:
                logging.warning("ComicInfo.xml is missing.")
                return False

    def process(self):
        self.reformat()

        if self.has_metadata():
            self.process_with_metadata()
        else:
            self.process_without_metadata()
            if self.has_metadata():
                self.process_with_metadata()

    def process_with_metadata(self):
        with MetadataExtraction(self.comic_info) as extractor:
            raw_comic_info = extractor.run()
        with MetadataProcessing(raw_comic_info) as cleaner:
            try:
                cleaned_comic_info = cleaner.run()
                new_name, publisher_int = cleaner.new_filename_and_folder()
            except PublisherNotKnown as e:
                logging.warning(f"Publisher unknown: {e.publisher_name}")
                insert_new_publisher(e.publisher_name)
                return

        for key, value in cleaned_comic_info.model_dump().items():
            if value == "PENDING":
                logging.error(f"Missing required {key} field.")
                # Need to remove ComicInfo.xml and
                # wait until sufficient data is supplied.
                return

        self.insert_into_db(cleaned_comic_info)
        self.extract_cover()
        self.move_to_publisher_folder(new_name, publisher_int)

    def process_without_metadata(self):
        result = run_tagging_process(self.filepath, API_KEY)
        if not result:
            return None
        results, actual = result
        ranked = self.rank_results(results, actual)
        selected = self.request_disambiguation(ranked, actual, results)
        if not selected:
            logging.info("User cancelled disambiguation process.")
            return None
        result = selected
        self.continue_tagging_from_user_match(result)
        return None

    def insert_into_db(self, cleaned_comic_info):
        logging.info("Starting inputting data to the database")
        if self.page_count is None:
            pagecount = self.get_pagecount()
            inputter = MetadataInputting(cleaned_comic_info, pagecount)
        else:
            inputter = MetadataInputting(cleaned_comic_info, self.page_count)
        try:
            inputter.run()
            flat_data = inputter.flatten_data()
        except Exception as e:
            raise ValueError(f"[Error] {e}")
        insert_into_fts5(flat_data)
        logging.info("Success! Added all data to the database")
        self.inputter = inputter

    def extract_cover(self):
        logging.info("Starting cover extraction")
        image_proc = ImageExtraction(
            self.filepath, ROOT_DIR / ".covers", self.primary_key
        )
        image_proc.run()

    def move_to_publisher_folder(self, new_name: str, publisher_int: int) -> None:
        for subdir in ROOT_DIR.iterdir():
            if subdir.is_dir() and subdir.name.startswith(str(publisher_int)):
                new_path = subdir / new_name
                shutil.move(self.original_filepath, new_path)
                logging.info(f"Moved file to {subdir.name}")

                try:
                    relative_path = new_path.relative_to(ROOT_DIR)
                    self.inputter.insert_filepath(relative_path)
                except ValueError as e:
                    logging.error(f"Failed to compute relative path: {e}")
                # TODO: Implement code to recover correct path, not urgent.
                logging.info("[INFO] Inserted filepath to database")
                self.inputter.conn.close()
                return

    def rank_results(self, all_results, comic_info):
        with ResultsFilter(all_results, comic_info, self.filepath) as filterer:
            filtered_results = filterer.present_choices()
        return filtered_results

    def request_disambiguation(
        self,
        results: list[tuple[ComicMatch, int]],
        actual_comic: RequestData,
        all_results: list[dict],
    ):
        match = self.display.get_user_match(  # type: ignore
            results, actual_comic, all_results, self.filepath
        )
        if match:
            return match
        return None

    def continue_tagging_from_user_match(self, match: dict):
        extract_and_insert(match, API_KEY, self.original_filename, self.filepath)


VALID_EXTENSIONS = {".cbz", ".cbr", ".zip"}
EXCLUDE = {
    "0 - Downloads",
    "1 - Marvel Comics",
    "2 - DC Comics",
    "3 - Image Comics",
    "4 - Dark Horse Comics",
    "5 - IDW Comics",
    "6 - Valiant Comics",
    "7 - 2000AD Comics",
    "8 - Urban Comics",
}


def run_tagger(display: QMainWindow):
    downloads_dir = ROOT_DIR / "0 - Downloads"
    for path in downloads_dir.rglob("*"):
        if path.is_dir() and path.name in EXCLUDE:
            continue
        if path.is_file() and any(
            path.name.lower().endswith(ext) for ext in VALID_EXTENSIONS
        ):
            logging.info(f"Starting to process {path.name}")
            new_id = generate_uuid()
            cont = MetadataController(new_id, path, display)
            cont.process()

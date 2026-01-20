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
        path: The filepath of the comic archive to be searched against.

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
        """
        Converts .cbr files into .cbz files.

        Raises:
            ValueError: If anything other than a .cbr or .cbz this error is raised.
        """
        temp_filepath = self.original_filepath
        if temp_filepath.suffix == ".cbr":
            temp_filepath = convert_cbz(temp_filepath)
            self.filepath = temp_filepath
        elif temp_filepath.suffix != ".cbz":
            raise ValueError("Wrong filetype.")

    def get_pagecount(self) -> int:
        """
        Gets the number of pages in the comic archive.

        Returns:
            int: The number of pages in the comic.
        """
        if self.filepath is None:
            logging.error("Filename must not be None")
            raise ValueError("Filename must not be None")
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

        Returns:
            bool: True if all required info is present, else False.
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

    def process(self) -> None:
        """
        This is the main control sequence for the tagging process. First it puts the comic
        into the correct format then it decides if its metadata is sufficient and then decides
        what to do from there.
        """
        self.reformat()

        if self.has_metadata():
            self.process_with_metadata()
        else:
            self.process_without_metadata()
            if self.has_metadata():
                self.process_with_metadata()

    def process_with_metadata(self) -> None:
        """
        This extracts all metadata from the embedded xml, cleans it so that the format is consistent
        across the app. Then it provides the comic with a new filename and filepath, finally it gets
        added to the database, its cover extracted and it is then moved to the correct folder.
        """
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
                raise ValueError(f"Missing required {key} field.")

        self.insert_into_db(cleaned_comic_info)
        self.extract_cover()
        self.move_to_publisher_folder(new_name, publisher_int)

    def process_without_metadata(self) -> None:
        """
        This runs the full tagging process; queries the ComicVine database to get the correct metadata,
        compiles this, renames the file and then extracts its cover, adds the comic to the database
        and finally moves the file to the correct folder.
        """
        tagger = run_tagging_process(self.filepath, API_KEY)
        if len(tagger.results) == 1:
            return tagger[0]
        elif len(tagger.results) > 1:
            ranked = self.rank_results(tagger.results, tagger.data)
            selected = self.request_disambiguation(ranked, tagger.data, tagger.results) 
            # TODO: Test this and then remove as wrong logic if there is only 1 good match.
            if not selected:
                logging.info("User cancelled disambiguation process.")
                return None
            return selected
            # self.continue_tagging_from_user_match(result)
        elif len(tagger.results) == 0:
            ranked = self.rank_results(tagger.potential_results, tagger.data)
            selected = self.request_disambiguation(ranked, tagger.data, tagger.potential_results)
            if not selected:
                logging.info("User cancelled disambiguation process.")
                return None
            return selected
            # self.continue_tagging_from_user_match(result)

    def insert_into_db(self, cleaned_comic_info: ComicInfo) -> None:
        """
        Adds all the relevant metadata for a comic into the database, this includes real-world
        metadata and in-world metadata.

        Args:
            cleaned_comic_info (ComicInfo): A pydantic model that contains all the relevant
                metadata for the comic.

        Raises:
            ValueError: If in the process of inputting there is an error, this is raised.
        """
        print("[INFO] Starting inputting data to the database")
        self.page_count = (
            self.get_pagecount() if self.page_count is None else self.page_count
        )
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
        """
        This extracts the cover image from the archive and adds it to the .covers folder in the
        root directory.
        """
        logging.info("Starting cover extraction")
       
        image_proc = ImageExtraction(
            self.filepath, ROOT_DIR / ".covers", self.primary_key
        )
        image_proc.run()

    def move_to_publisher_folder(self, new_name: str, publisher_int: int) -> None:
        """
        Moves the comic archive to the correct folder, depending on the publisher.

        Args:
            new_name (str): The name of the comic archive that was decided from metadata.
            publisher_int (int): The unique ID of the publisher, these align with the database ID's.
        """
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
                logging.info("Inserted filepath to database")
                self.inputter.conn.close()

    def rank_results(self, all_results, comic_info):
        with ResultsFilter(all_results, comic_info, self.filepath) as filterer:
            return filterer.present_choices()

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

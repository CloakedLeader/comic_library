import logging
import os
import shutil
import sqlite3
import zipfile
from typing import Optional

from defusedxml import ElementTree as ET
from dotenv import load_dotenv
from PySide6.QtWidgets import QMainWindow

from cover_processing import ImageExtraction
from database.db_input import MetadataInputting, insert_new_publisher
from extract_meta_xml import MetadataExtraction
from file_utils import convert_cbz, generate_uuid, get_ext
from classes.helper_classes import ComicInfo
from metadata_cleaning import MetadataProcessing, PublisherNotKnown
from search import insert_into_fts5
from tagging_controller import RequestData, extract_and_insert, run_tagging_process
from comic_match_logic import ResultsFilter

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

load_dotenv()
API_KEY = os.getenv("API_KEY")


def get_comicid_from_path(
    path: str,
) -> int:
    """
    Finds the ID of the comic in the database from its filepath.

    Args:
        path: the filepath of the comic archive to be searched against.

    Raises:
        LookupError: if the comic is not found in the database.
    """
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM comics WHERE path = ?", (path,))
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
    def __init__(self, primary_key: str, filepath: str, display: QMainWindow):
        self.primary_key = primary_key
        self.original_filepath = filepath
        self.display = display
        self.original_filename = os.path.basename(filepath)
        self.filepath: Optional[str] = filepath
        self.filename: Optional[str] = os.path.basename(filepath)
        self.comic_info: Optional[ComicInfo] = None

    def reformat(self) -> None:
        temp_filepath = self.original_filepath
        if get_ext(temp_filepath) == ".cbr":
            temp_filepath = convert_cbz(temp_filepath)
            self.filepath = temp_filepath
        elif get_ext(temp_filepath) != ".cbz":
            raise ValueError("Wrong filetype.")

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
            print("Filename must not be None")
            return False
        with zipfile.ZipFile(self.filepath, "r") as archive:
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
                                print(f"ComicInfo.xml is missing tags: {missing}")
                                return False
                            else:
                                print("ComicInfo.xml is valid and complete")
                                return True
                        else:
                            print("No content in XML")
                            return False

                    except ET.ParseError:
                        print("ComicInfo.xml is present but not valid xml")
                        return False
            else:
                print("ComicInfo.xml is missing.")
                return False

    def process(self):
        self.reformat()
        self.comic_info = ComicInfo(
            primary_key=self.primary_key,
            filepath=self.filepath,
            original_filename=self.original_filename,
        )
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
                print(f"[WARN] Publisher unknown: {e.publisher_name}")
                insert_new_publisher(e.publisher_name)
                return

        for key, value in cleaned_comic_info.model_dump().items():
            if value == "PENDING":
                print(f"[ERROR] Missing required {key} field.")
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
            print("[INFO] User cancelled disambiguation")
            return None
        result = selected
        self.continue_tagging_from_user_match(result)
        return None

    def insert_into_db(self, cleaned_comic_info):
        print("[INFO] Starting inputting data to the database")
        inputter = MetadataInputting(cleaned_comic_info)
        try:
            inputter.run()
            flat_data = inputter.flatten_data()
        except Exception as e:
            print(f"[Error] {e}")
        insert_into_fts5(flat_data)
        print("[SUCCESS] Added all data to the database")
        self.inputter = inputter

    def extract_cover(self):
        print("[INFO] Starting cover extraction")
        image_proc = ImageExtraction(
            self.filepath, "D://adams-comics//.covers", self.primary_key
        )
        image_proc.run()

    def move_to_publisher_folder(self, new_name, publisher_int):
        for dirpath, dirnames, _ in os.walk("D://adams-comics"):
            for dirname in dirnames:
                if str(dirname).startswith(str(publisher_int)):
                    dir_path = os.path.join(dirpath, dirname)
                    new_path = os.path.join(dir_path, new_name)
                    shutil.move(self.original_filepath, new_path)
                    print(f"[INFO] Moved file to {dir_path}")
                    self.inputter.insert_filepath(new_path)
                    print("[INFO] Inserted filepath to database")
                    self.inputter.conn.close()
                    return

    def rank_results(self, all_results, comic_info):
        with ResultsFilter(all_results, comic_info, self.filepath) as filterer:
            filtered_results = filterer.present_choices()
        return filtered_results

    def request_disambiguation(self, results: list[dict],
                               actual_comic: RequestData, all_results: list[dict]):
        match = self.display.get_user_match(results, actual_comic,
                                            all_results, self.filepath)
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
    for dirpath, dirnames, filenames in os.walk("D://adams-comics//0 - Downloads"):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE]
        for filename in filenames:
            if not any(filename.lower().endswith(ext) for ext in VALID_EXTENSIONS):
                continue
            print(f"Starting to process {filename}")
            full_path = os.path.join(dirpath, filename)
            new_id = generate_uuid()
            cont = MetadataController(new_id, full_path, display)
            cont.process()

import logging
import os
import shutil
import sqlite3
import time
import zipfile
from typing import Optional

from defusedxml import ElementTree as ET
from dotenv import load_dotenv
from watchdog.events import FileSystemEventHandler

from cover_processing import ImageExtraction
from db_input import MetadataInputting, insert_new_publisher
from extract_meta_xml import MetadataExtraction
from file_utils import convert_cbz, generate_uuid, get_ext
from helper_classes import ComicInfo
from metadata_cleaning import MetadataProcessing, PublisherNotKnown
from search import insert_into_fts5
from tagging_controller import run_tagging_process

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("log.txt")],
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


# ===================
# Watchdog Module
# ===================


path_to_obs = os.getenv("PATH_TO_WATCH")


class DownloadsHandler(FileSystemEventHandler):
    """
    Watches a directory for new files and processes them when they appear.

    Attributes:
        None

    Methods:
        on_created(event): Triggered when a file is created. Waits until file
    is stable then processes it.
        on_moved(event): Triggered when a file is moved. Handles processing
    if moved to the watched folder.
        on_deleted(event): Triggered when a file is deleted.
        is_file_ready(filepath, stable_time, check_interval): Checks if a file has
    stopped changing size to ensure it's fully written.
        process_file(path, dest_path_temp): Moves a stable file to a destination,
    renaming if needed.
        handle_new_file(path): Inserts a new comic into the database and converts
    formats if necessary.
    """

    def on_created(self, event: FileSystemEventHandler) -> None:
        """
        Called when a new file is created in the watched directory.

        Args:
            event(FileSystemEvent): The file system event triggered.
        """
        if event.is_directory:
            return

        filepath = event.src_path
        filename = os.path.basename(filepath)

        if filename.endswith(".part"):
            logging.info(f"Ignoring partial file: {filename}")
            return

        logging.info(f"Detected new file: {filename}")

        time.sleep(2)

        if not self.is_file_ready(filepath):
            logging.warning(f"File not stable yet: {filename}")
            return

        new_key = generate_uuid()
        cont = MetadataController(new_key, filepath)
        cont.process()

    def on_moved(self, event: FileSystemEventHandler) -> None:
        """
        Called when a file is moved.

        Args:
            event(FileSystemEvent): The file system move event.
        """
        if event.dest_path == path_to_obs:
            if not event.is_directory:
                file_path = event.src_path
                logging.debug(f"New file detected: {file_path}")
                self.handle_new_file(file_path)

    def on_deleted(self, event: FileSystemEventHandler) -> None:
        """
        Called when a file is deleted.

        Args:
            event (FileSystemEvent): The file system delete event.
        """
        logging.debug(f"Detected a file deletion: {event.src_path}")

    def is_file_ready(
        self, filepath: str, stable_time: int = 5, check_interval: int = 1
    ) -> bool:
        """
        Checks to see if the file size has stabilised over time,
        indicating it's fully written.

        Args:
            filepath: Path to newly detected file.
            stable_time: Number of consectutive stable intervals.
        intervals before confirming readiness.
            check_interval: The number of seconds to wait between intervals.

        Returns:
            bool: True if file is stable and ready to be moved, False otherwise.
        """
        prev_size = -1
        stab_counter = 0
        while stab_counter < stable_time:
            try:
                current_size = os.path.getsize(filepath)
            except FileNotFoundError:
                logging.warning(f"File {filepath} disappeared.")
                return False

            if current_size == prev_size:
                stab_counter += 1
            else:
                stab_counter = 0
                prev_size = current_size

            time.sleep(check_interval)

        return True


class MetadataController:
    def __init__(self, primary_key: str, filepath: str):
        self.primary_key = primary_key
        self.original_filepath = filepath
        self.original_filename = os.path.basename(filepath)
        self.filepath: Optional[str] = filepath
        self.filename: Optional[str] = os.path.basename(filepath)
        self.comic_info: Optional[ComicInfo] = None

    def reformat(self) -> None:
        temp_filepath = self.original_filepath
        if get_ext(temp_filepath) == ".cbr":
            temp_filepath = convert_cbz(temp_filepath)
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
            raise ValueError("Filename must not be None")
        with zipfile.ZipFile(self.filepath, "r") as archive:
            if "ComicInfo.xml" in archive.namelist():
                with archive.open("ComicInfo.xml") as xml_file:
                    try:
                        tree = ET.parse(xml_file)
                        root = tree.getroot()
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
        run_tagging_process(self.filepath, API_KEY)

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


def run_tagger():
    for dirpath, dirnames, filenames in os.walk("D://adams-comics//0 - Downloads"):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE]
        for filename in filenames:
            if not any(filename.lower().endswith(ext) for ext in VALID_EXTENSIONS):
                continue
            print(f"Starting to process {filename}")
            full_path = os.path.join(dirpath, filename)
            new_id = generate_uuid()
            cont = MetadataController(new_id, full_path)
            cont.process()

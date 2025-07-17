import logging
import os
import sqlite3
import time
import zipfile
from typing import Optional

from defusedxml import ElementTree as ET
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from db_input import insert_new_publisher
from extract_meta_xml import MetadataExtraction
from file_utils import convert_cbz, generate_uuid, get_ext
from helper_classes import ComicInfo
from metadata_cleaning import MetadataProcessing, PublisherNotKnown

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("log.txt")],
)


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
        self.filepath: Optional[str] = None
        self.filename: Optional[str] = None
        self.comic_info: Optional[ComicInfo] = None

    def rename_and_reformat(self) -> None:
        temp_filepath = self.original_filepath
        if get_ext(temp_filepath) == ".cbr":
            temp_filepath = convert_cbz(temp_filepath)
        elif get_ext(temp_filepath) != ".cbz":
            raise ValueError("Wrong filetype.")

        directory = os.path.dirname(temp_filepath)
        new_name = f"{self.primary_key}.cbz"
        new_path = os.path.join(directory, new_name)

        os.rename(temp_filepath, new_path)

        self.filepath = new_path
        self.filename = new_name

    def has_metadata(self) -> bool:
        """
        Checks that the required metadata fields are complete with some info
        e.g. that they are not blank.

        Args:
        required: A list of the fields that must be present.

        Returns:
        True if all required info is present, else False.
        """

        required_fields = ["Title", "Series", "Year", "Number", "Writer", "Summary"]
        if self.filepath is None:
            raise ValueError("Filename must not be None")
        with zipfile.ZipFile(self.filepath, "r") as archive:
            if "ComicInfo.xml" in archive.namelist():
                with archive.open("ComicInfo.xml") as xml_file:
                    try:
                        tree = ET.parse(xml_file)
                        root = tree.getroot()
                        missing = [
                            tag for tag in required_fields if root.find(tag) is None
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
        self.rename_and_reformat()
        self.comic_info = ComicInfo(
            primary_key=self.primary_key,
            filepath=self.filepath,
            original_filename=self.original_filename,
        )
        while True:
            if self.has_metadata():
                with MetadataExtraction(self.comic_info) as extractor:
                    raw_comic_info = extractor.run()
                with MetadataProcessing(raw_comic_info) as cleaner:
                    try:
                        cleaned_comic_info = cleaner.run()
                    except PublisherNotKnown as e:
                        print(e)
                        unknown_publisher = e.publisher_name
                        # Start new publisher process.
                        insert_new_publisher(unknown_publisher)
                        continue

                missing_fields = [
                    k for k, v in cleaned_comic_info.model_dump().items() if v is None
                ]
                if missing_fields:
                    # Need to call the entire tagging process here.
                    pass
                # Then call the database insertion process.
                break  # Finished successfully, exit the loop
            else:
                # Call the entire tagging process.
                # Call the xml creation process.
                # Call the database insertion process.
                pass

        # Now the file should have complete metdata and be in the database.
        # Rename to permanent name.
        # Move to correct folder or place.


obs = Observer()
obs.schedule(DownloadsHandler(), path_to_obs, recursive=False)
obs.start()
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    obs.stop()
    obs.join()

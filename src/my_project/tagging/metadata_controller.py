import calendar
import logging
import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import Optional

from defusedxml import ElementTree as ET
from PySide6.QtWidgets import QMainWindow

from my_project.classes.helper_classes import ComicInfo, ComicVineIssueStruct
from my_project.config.config_manager import ConfigManager
from my_project.database.db_input import MetadataInputting, insert_new_publisher
from my_project.database.gui_repo_worker import RepoWorker
from my_project.database.search import FTS5Inserter
from my_project.tagging.applier import TagApplication
from my_project.tagging.comic_match_logic import ComicMatch, ResultsFilter
from my_project.tagging.extract_meta_xml import MetadataExtraction
from my_project.tagging.metadata_cleaning import MetadataProcessing, PublisherNotKnown
from my_project.tagging.metadata_inserter import MetadataInserter
from my_project.tagging.tagging_controller import (  # extract_and_insert
    MatchCode,
    RequestData,
    run_tagging_process,
)
from my_project.utils.cover_processing import ImageExtraction
from my_project.utils.file_utils import convert_cbz, generate_uuid

logger = logging.getLogger(__name__)

SERIES_OVERRIDES = [
    ("tpb", 1, "TPB"),
    ("omnibus", 2, "Omni"),
    ("modern era epic collection", 4, "MEC"),
    ("epic collection", 3, "EC"),
]


# use Amazing Spider-Man Modern Era Epic Collection: Coming Home

# File Naming System: [Series_Name][Start_Year] -
# [Collection_Type] [Volume_Number] ([date in month/year])
# User Visible Title: [Series] [star_year] -
# [collection type] Volume [volume_number]: [Title] [month] [year]


class MetadataController:
    def __init__(
        self,
        primary_key: str,
        filepath: Path,
        display: QMainWindow,
        config_manager: ConfigManager,
    ):
        self.config_manager = config_manager
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

    @staticmethod
    def sanitise(filename: str) -> str:
        santised = re.sub(r'[<>:"/\\|?*]', "-", filename)
        santised = santised.rstrip(" .")
        return santised

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
            logger.error("Filename must not be None")
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
        logger.info("Checking present metadata.")
        if self.filepath is None:
            logger.error("Filename must not be None")
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
                                logger.error(
                                    f"ComicInfo.xml is missing tags: {missing}"
                                )
                                return False
                            else:
                                logger.info("ComicInfo.xml is valid and complete")
                                return True
                        else:
                            logger.warning("No content in XML")
                            return False

                    except ET.ParseError:
                        logger.warning("ComicInfo.xml is present but not valid xml")
                        return False
            else:
                logger.warning("ComicInfo.xml is missing.")
                return False

    def process(self) -> None:
        """
        This is the main control sequence for the tagging process. First it puts the comic
        into the correct format then it decides if its metadata is sufficient and then decides
        what to do from there.
        """
        self.reformat()
        has_metadata = self.has_metadata()

        if has_metadata:
            raw_comic_metadata: ComicInfo = self.get_embedded_metadata()
        else:
            logger.info("Starting search for comic in ComicVine database.")
            tag_applier = self.get_one_result()

            if tag_applier:
                logger.info("Search results lead to one result.")
                raw_comic_metadata = tag_applier.create_metadata_dict()
                logger.info("Metadata dictionary created.")
            else:
                logger.error("No comic with which to match.")
                return
                # raise RuntimeError("No comic with which to match.")
        clean_comic_metadata: ComicInfo = self.clean_embedded_metadata(
            raw_comic_metadata
        )
        logger.info("Cleaned metadata dictionary.")
        for key, value in clean_comic_metadata.model_dump().items():
            if value == "PENDING":
                logger.error(f"Missing required {key} field.")
                # Need to remove ComicInfo.xml and
                # wait until sufficient data is supplied.
                raise ValueError(f"Missing required {key} field.")

        new_name, publisher_int = self.create_name(clean_comic_metadata)

        inserter = MetadataInserter(clean_comic_metadata, self.filepath)
        if inserter.create_valid_struc():
            inserter.run_inserter()
        else:
            raise ValueError("Missing required fields in metadata.")

        self.insert_into_db(clean_comic_metadata)
        self.extract_cover()
        self.move_to_publisher_folder(new_name, publisher_int)

        # This all needs to be split up into modular components so the different aspects, db insertion, cover extracting
        # are independent and use the same data types to ensure consistency.

    def create_name(self, clean_metadata: ComicInfo) -> tuple[str, int]:
        date_suffix = (
            f"{calendar.month_abbr[clean_metadata.month]} {clean_metadata.year}"  # type: ignore
        )
        volume_num = clean_metadata.volume_num
        collection_id = clean_metadata.collection_type
        collection_name = ""
        for _, val, abbr in SERIES_OVERRIDES:
            if val == collection_id:
                collection_name = abbr.strip()
                break
        series_name = self.sanitise(str(clean_metadata.series)).strip()
        title_name = self.sanitise(str(clean_metadata.title)).strip()
        filename = f"{series_name} - {title_name} {collection_name} #0{volume_num} ({date_suffix}).cbz"  # noqa: E501
        filename = self.sanitise(filename).strip()
        return filename, clean_metadata.publisher_id  # type: ignore

    def get_embedded_metadata(self) -> ComicInfo:
        with MetadataExtraction(self.comic_info) as extractor:
            return extractor.run()

    def clean_embedded_metadata(self, raw_data: ComicInfo) -> ComicInfo:
        with MetadataProcessing(raw_data, self.config_manager) as cleaner:
            try:
                cleaned_comic_info = cleaner.run()
                # new_name, publisher_int = cleaner.new_filename_and_folder()
                # ! Take this function from metadata_cleaning and use in this class.
                return cleaned_comic_info
            except PublisherNotKnown as e:
                logger.warning(f"Publisher unknown: {e.publisher_name}")
                insert_new_publisher(
                    e.publisher_name, self.config_manager.config.database.path
                )
                return self.clean_embedded_metadata(
                    raw_data
                )  # This may cause infinite loop!

    def process_with_metadata(self) -> None:
        """
        This extracts all metadata from the embedded xml, cleans it so that the format is consistent
        across the app. Then it provides the comic with a new filename and filepath, finally it gets
        added to the database, its cover extracted and it is then moved to the correct folder.
        """
        with MetadataExtraction(self.comic_info) as extractor:
            raw_comic_info = extractor.run()
        with MetadataProcessing(raw_comic_info, self.config_manager) as cleaner:
            try:
                cleaned_comic_info = cleaner.run()
                new_name, publisher_int = cleaner.new_filename_and_folder()
            except PublisherNotKnown as e:
                logger.warning(f"Publisher unknown: {e.publisher_name}")
                insert_new_publisher(
                    e.publisher_name, self.config_manager.config.database.path
                )
                return

        for key, value in cleaned_comic_info.model_dump().items():
            if value == "PENDING":
                logger.error(f"Missing required {key} field.")
                # Need to remove ComicInfo.xml and
                # wait until sufficient data is supplied.
                raise ValueError(f"Missing required {key} field.")

        self.insert_into_db(cleaned_comic_info)
        self.extract_cover()
        self.move_to_publisher_folder(new_name, publisher_int)

    def get_one_result(self) -> Optional[TagApplication]:
        """
        This runs the full tagging process; queries the ComicVine database to get the correct metadata,
        compiles this, renames the file and then extracts its cover, adds the comic to the database
        and finally moves the file to the correct folder.
        """
        tagger, matchcode = run_tagging_process(
            self.filepath, self.config_manager.config.comicvine.api_key
        )

        if matchcode == MatchCode.ONE_MATCH:
            publisher_info = tagger.get_publisher_info(tagger.results[0].volume.id)
            detailed_info = tagger.http.detail_get_request(tagger.results[0].id)
            return TagApplication(
                detailed_info,
                publisher_info,
                self.config_manager.config.comicvine.api_key,
                self.filename,
            )
        elif matchcode == MatchCode.MULTIPLE_MATCHES:
            ranked = self.rank_results(tagger.results, tagger.data)
            selected = self.request_disambiguation(ranked, tagger.data, tagger.results)
            # TODO: Test this and then remove as wrong logic if there is only 1 good match.
            if not selected:
                logger.info("User cancelled disambiguation process.")
                return None
            publisher_info = tagger.get_publisher_info(selected.volume.id)
            detailed_info = tagger.http.detail_get_request(selected.id)
            return TagApplication(
                detailed_info,
                publisher_info,
                self.config_manager.config.comicvine.api_key,
                self.filename,
            )
        else:
            ranked = self.rank_results(tagger.potential_results, tagger.data)
            selected = self.request_disambiguation(
                ranked, tagger.data, tagger.potential_results
            )
            if not selected:
                logger.info("User cancelled disambiguation process.")
                return None
            publisher_info = tagger.get_publisher_info(selected.volume.id)
            detailed_info = tagger.http.detail_get_request(selected.id)
            return TagApplication(
                detailed_info,
                publisher_info,
                self.config_manager.config.comicvine.api_key,
                self.filename,
            )

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
        logger.info("Starting inputting data to the database")
        self.page_count = (
            self.get_pagecount() if self.page_count is None else self.page_count
        )
        inputter = MetadataInputting(
            cleaned_comic_info, self.page_count, self.config_manager
        )
        try:
            inputter.run()
            flat_data = inputter.flatten_data()
        except Exception as e:
            raise ValueError(f"[Error] {e}") from e
        with FTS5Inserter(self.config_manager) as ftst5inserter:
            ftst5inserter.insert_into_fts5(flat_data)
        logger.info("Success! Added all data to the database")
        self.inputter = inputter

    def extract_cover(self):
        """
        This extracts the cover image from the archive and adds it to the .covers folder in the
        root directory.
        """
        logger.info("Starting cover extraction")

        image_proc = ImageExtraction(
            self.filepath,
            self.config_manager.config.comicsroot.path / ".covers",
            self.primary_key,
        )
        image_proc.run()

    def move_to_publisher_folder(self, new_name: str, publisher_int: int) -> None:
        """
        Moves the comic archive to the correct folder, depending on the publisher.

        Args:
            new_name (str): The name of the comic archive that was decided from metadata.
            publisher_int (int): The unique ID of the publisher, these align with the database ID's.
        """
        for subdir in self.config_manager.config.comicsroot.path.iterdir():
            if subdir.is_dir() and subdir.name.startswith(str(publisher_int)):
                new_path = subdir / new_name
                shutil.move(self.original_filepath, new_path)
                logger.info(f"Moved file to {subdir.name}")

                try:
                    relative_path = new_path.relative_to(
                        self.config_manager.config.comicsroot.path
                    )
                    self.inputter.insert_filepath(relative_path)
                except ValueError as e:
                    logger.error(f"Failed to compute relative path: {e}")
                # TODO: Implement code to recover correct path, not urgent.
                logger.info("Inserted filepath to database")
                self.inputter.conn.close()

    def rank_results(self, all_results, comic_info):
        with ResultsFilter(all_results, comic_info, self.filepath) as filterer:
            return filterer.present_choices()

    def request_disambiguation(
        self,
        results: list[tuple[ComicMatch, int]],
        actual_comic: RequestData,
        all_results: list[ComicVineIssueStruct],
    ) -> Optional[ComicVineIssueStruct]:
        match = self.display.get_user_match(  # type: ignore
            results, actual_comic, all_results, self.filepath
        )
        if match:
            return match
        return None


VALID_EXTENSIONS = {".cbz", ".cbr"}
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


def run_tagger(display: QMainWindow, config_manager: ConfigManager):
    downloads_dir = config_manager.config.comicsroot.path / "0 - Downloads"
    for path in downloads_dir.rglob("*"):
        if path.is_dir() and path.name in EXCLUDE:
            continue
        if path.is_file() and any(
            path.name.lower().endswith(ext) for ext in VALID_EXTENSIONS
        ):
            logger.info(f"Starting to process {path.name}")
            with RepoWorker(config_manager) as worker:
                if worker.comic_in_db(path):
                    return None
            new_id = generate_uuid()
            cont = MetadataController(new_id, path, display, config_manager)
            cont.process()

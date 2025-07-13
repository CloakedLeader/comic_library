import logging
import os
import random
import re
import sqlite3
import defusedxml.ElementTree as ET
import zipfile
from io import BytesIO
from typing import Optional, Tuple, Union, Any, TypedDict
from pathlib import Path
import tempfile

import Levenshtein
from fuzzywuzzy import fuzz
from PIL import Image
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from word2number import w2n

from helper_classes import ComicInfo

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("log.txt")],
)


def pad(n: int) -> str:
    return f"{n:04}" if n < 1000 else str(n)


# NEED TO WORK ON THIS FUNCTION

# def sort_imgs(filename: str) -> int:
#     numbers = re.findall(r"\d+", filename)
#     return int(numbers[-1]) if numbers else -1


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


download_path = os.getenv("DEST_FILE_PATH")


# ===========================================
# Advanced parsing that requires extra logic
# ===========================================

# use Amazing Spider-Man Modern Era Epic Collection: Coming Home

# File Naming System: [Series_Name][Start_Year] -
# [Collection_Type] [Volume_Number] ([date in month/year])
# User Visible Title: [Series] [star_year] -
# [collection type] Volume [volume_number]: [Title] [month] [year]


class MetadataExtraction:
    def __init__(self, path: str, temp_dir: str | None = None) -> None:
        self.filepath: str = path
        self.temp_dir: str = temp_dir if temp_dir else tempfile.mkdtemp()
        self.extracted: bool = False
        self.metadata_root = None

    def extract(self) -> None:
        if not self.extracted:
            with zipfile.ZipFile(self.filepath, "r") as zip_ref:
                zip_ref.extractall(self.temp_dir)
            self.extracted = True

    def get_metadata(self) -> bool:
        """
        Extracts the ComicInfo.xml metadata file from an archive.

        Returns:
            True if the ComicInfo was found, else False.

        Raises:
            zipfile.BadZipFile: If the file is not a valid ZIP archive.
            FileNotFoundError: If the file is not found.
            KeyError: If ComicInfo.xml is not found in the archive.
            ET.ParseError: If ComicInfo.xml is not valid XML.
            Any other exceptions encountered during file access/parsing.
        """
        self.extract()
        if self.metadata_root is not None:
            return True
        xml_path = os.path.join(self.temp_dir, "ComicInfo.xml")
        if os.path.exists(xml_path):
            tree = ET.parse(xml_path)
            self.metadata_root = tree.getroot()
            return True
        else:
            return False
  
    def has_complete_metadata(self, required: list) -> bool:
        """
        Checks that the required metadata fields are complete with some info
        e.g. that they are not blank.

        Args:
        required: A list of the fields that must be present.

        Returns:
        True if all required info is present, else False.
        """
        for field in required:
            try:
                self.get_text(field)
            except KeyError:
                return False
        return True

    def get_text(self, tag: str) -> str:
        """
        Searches for results under the tag given. Returns the stripped content.

        Args:
            tag: The section to search for (e.g. writer, summary etc).

        Returns:
            The stripped text from the tag.

        Raises:
            KeyError: If the tag is missing or has no text content.
        """
        element = self.metadata_root.find(tag)
        if element is not None and element.text:
            return element.text.strip()
        else:
            raise KeyError(f"No info inside tag: {tag}.")
 
    def easy_parsing(self, field: str, as_type: type = str) -> str | int:
        """
        Returns metadata from the corresponding field by parsing an XML tree.
        Assumes ComicInfo.xml has already been verified to exist and be readable.

        Args:
        field: The name of the metadata field.
        as_type: The type that the metadata must be returned as.
            Required as all metadata fields are strings by default
            but some must be integers.

        Returns:
        The metadata inside that field, either a string or integer.
        Never type None.
        """
        text = self.get_text(field)
        if text is None:
            raise KeyError(f"Field '{field}' not found in metadata.")

        try:
            return as_type(text)
        except ValueError as e:
            raise TypeError(
                f"Could not convert field '{field}' to {as_type.__name__}"
            ) from e
       
    def parse_characters_or_teams(self, field: str) -> list[str]:
        """
        Finds all the characters or teams affliated with the comic book.

        Args:
        field: Whether to search under the characters or teams field.

        Returns:
        A list of the corresponding people.
        """
        seen = set()
        out = []
        list_string = self.easy_parsing(field)
        items = [p.strip() for p in list_string.split(",")]
        for item in items:
            if item not in seen:
                seen.add(item)
                out.append(item)

        return out

    def parse_creators(self, fields: list) -> list[tuple]:
        """
        Finds all the creators affliated with the book.

        Args:
        fields: A list of job titles of the creator(s) for example:
            'Writer' or 'Penciller'

        Returns:
        A list of tuples of people and their role, for example:
        (John Byrne, Penciller)
        """
        creator_role_list = []
        seen_per_role = {field: set() for field in fields}
        for field in fields:
            list_string = self.easy_parsing(field)
            people_raw = [p.strip() for p in list_string.split(",")]
            for person in people_raw:
                if person not in seen_per_role[field]:
                    seen_per_role[field].add(person)
                    creator_role_list.append((person, field))
        return creator_role_list
  
    def to_dict(self) -> dict[str, Any]:
        roles = ["Writer", "Penciller", "CoverArtist", "Inker", "Colorist", "Letterer", "Editor"]
        final_dict: ComicInfo = {
            "title": self.easy_parsing("Title"),
            "series": self.easy_parsing("Series"),
            "volume_num": self.easy_parsing("Number", int),
            "publisher": self.easy_parsing("Publisher"),
            "month": self.easy_parsing("Month", int),
            "year": self.easy_parsing("Year", int),
            "file_path": self.filepath,
            "description": self.easy_parsing("Summary"),
            "creators": self.parse_creators(roles),
            "characters": self.parse_characters_or_teams("Characters"),
            "teams": self.parse_characters_or_teams("Teams")
        }
        return final_dict
        
    def extract_metadata(self) -> dict[str, Any]:
        required_fields = ["Title", "Series", "Year", "Number", "Writer", "Summary"]
        self.extract()
        if self.has_complete_metadata(required_fields):
            return self.to_dict()


class MetadataProcessing:
    def __init__(self, raw_dict: ComicInfo) -> None:
        self.raw_info = raw_dict
        self.filepath = raw_dict["filepath"]
        self.title_info = None

    PATTERNS: list[re.Pattern] = [
        re.compile(r"\bv(?<num>)\d{1,3}\b", re.I),

        re.compile(r"\b(?<num>\d{3})\b"),

        re.compile(r"\bvol(?:ume)?\.?\s*(?P<num>\d{1,3})\b", re.I),
    ]
        
    SPECIAL_PATTERN = re.compile(r"\bv(?P<volume>\d{1,3})\s+(?P<issue>\d{2,3})\b)", re.I)
    
    @staticmethod
    def normalise_publisher_name(name: str) -> str:
        suffixes = ["comics", "publishing", "group", "press", "inc.", "inc", "llc"]
        tokens = name.replace("&", "and").lower().split()
        return " ".join([t for t in tokens if t not in suffixes])
    
    @staticmethod
    def title_case(title: str) -> str:
        # Need to also make this capitalise things like X-Men not X-men.
        minor_words = {
            'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'in',
            'nor', 'of', 'on', 'or', 'so', 'the', 'to', 'up', 'yet'
        }

        words = title.lower().split()
        if not words:
            return ""
        
        result = []
        for i, word in enumerate(words):
            if i == 0 or i == len(words) - 1 or word not in minor_words:
                result.append(word.capitalize())
            else:
                result.append(word)        
        return " ".join(result)

    def match_publisher(self, raw_pub_name: str) -> int:
        """
        Matches the natural language name of a publisher from metadata
        to an entry in the list of known publishers with numbered keys from the sql table.
        This uses fuzzy matches due to alterations of publisher names.

        Args:
            raw_pub_name: The string extracted from ComicInfo.xml to be matched.

        Returns:
            The ID of the best-matching known publisher.

        Raises:
            KeyError: If no known publisher matches closely enough.
        """
        known_publishers = [
            (1, "Marvel Comics", "marvel"),
            (2, "DC Comics", "dc"),
            (3, "Image Comics", "image"),
            (4, "Dark Horse Comics", "dark horse"),
            (5, "IDW Comics", "idw"),
            (6, "Valiant Comics", "valiant"),
            (7, "2000AD Comics", "2000ad"),
        ]
        best_score = 0
        best_match = None
        normalised_pub_name = self.normalise_publisher_name(raw_pub_name)
        for pub_id, pub_name, clean_name in known_publishers:
            score = fuzz.token_set_ratio(normalised_pub_name, clean_name)
            if score > best_score:
                best_match = (pub_id, pub_name)
        if best_score >= 80 and best_match:
            return best_match[0]
        else:
            raise KeyError(f"Publisher '{raw_pub_name} not known.")
       
    def title_parsing(self) -> dict[str, str | int] | None:
        """
        Parses the title from the ComicInfo.xml to determine
        collection type, series name, title name and issue number.
        Tries to avoid ambigous title names.

        Returns:
            A dictionary with fields:
                - title: a string
                - series: a string
                - collection_type: an integer corresponding to the series_overrides
                    table
                - issue_num: an integer

        Raises:
            If issue number is zero, this signifies an error in the processing.
    """
        series_overrides = [
            ("tpb", 1),
            ("omnibus", 2),
            ("modern era epic collection", 4),
            ("epic collection", 3)
        ]
       
        out = {
            "title": str,
            "series": str,
            "collection_type": int,
            "issue_num": int
        }
        common_title_words = {"tpb", "hc"}

        title_raw = self.raw_info["title"].lower()
        series_raw = self.raw_info["series"].lower()

        if ":" in series_raw:
            series_name, collection_title = map(str.strip, series_raw.split(":", 1))
        elif ":" in title_raw:
            _, collection_title = map(str.strip, title_raw.split(":", 1))
            series_name = series_raw
        else:
            series_name = series_raw
            collection_title = title_raw

        for i in common_title_words:
            if i == collection_title:
                collection_title = series_name

        collection_type = 1
        for keyword, type_id in series_overrides:
            if keyword in series_name.lower():
                collection_type = type_id
                break
            if keyword in collection_title.lower():
                collection_type = type_id
                break
       
        volume_match = re.match(
            r"(?:vol(?:ume)?|book)\.?\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*[:\-]?\s*(.*)",
            title_raw, re.I
        )

        issue_number = None

        if volume_match:
            num_text = volume_match.group(1).lower()
            rest_title = volume_match.group(2).strip().lower()

            if num_text.isdigit():
                issue_number = int(num_text)
            else:
                try:
                    issue_number = w2n.word_to_num(num_text)
                except ValueError:
                    issue_number = 0  # Need a logic check later, 0 signals an error.

        if rest_title:
            collection_title = rest_title

        out["title"] = self.title_case(collection_title)
        out["series"] = self.title_case(series_name)
        out["collection_type"] = collection_type
        out["issue_num"] = issue_number

        self.title_info = out

        return out

    def check_issue_numbers_match(self) -> bool:
        if self.title_info is None:
            self.title_parsing()
        return self.raw_info["volume_num"] == self.title_info["issue_num"]
  
    def extract_volume_num_from_filepath(self) -> tuple[int, int]:
        fname = os.path.basename(self.filepath)
      
        for pat in self.PATTERNS:
            m = pat.search(fname)
            if m:
                volume = int(m.group("num").lstrip("0") or "0")
                return volume, 0

        m = self.SPECIAL_PATTERN.search(fname)
        if m:
            volume = int(m.group("volume").lstrip("0") or "0")
            issue = int(m.group("issue").lstrip("0") or "0")
            return volume, issue
     
        return 0, 0
    
    def volume_number_parsing(self) -> int:
        if self.check_issue_numbers_match():
            return int(self.title_info["volume_num"])
        #  Need extra logic here to get the correct volume number
      


class ImageExtraction:
    def __init__(self, path: str) -> None:
        self.filepath = path
        self.image_names : list[str] = self.get_namelist()
        self.cover_bytes : bytes = None

    @staticmethod
    def score(name: str) -> tuple[int, int, str]:
        COVER_CUES = re.compile(r"\b(?:cover|front|fc)\b", re.IGNORECASE)
        NUMBERS = re.compile(r"\d+")
        stem = Path(name)
        lowered = stem.lower()

        if COVER_CUES.search(lowered) or lowered.endswith("00"):
            return (0, 0, name)
        
        numbers = [int(n) for n in NUMBERS.findall(stem)]
        for num in numbers:
            if num in (0, 1):
                return (1, num, name)
        
        if numbers:
            return (2 + min(numbers), min(numbers), name)
    
        return (10, 0, name)

    def get_namelist(self) -> list[str]:
        with zipfile.ZipFile(self.filepath, "r") as zip_ref:
            images = [f for f in zip_ref.namelist() if f.endswith(".jpg", ".jpeg", ".png")]
        return images

    def choose_cover(self) -> str:
        """
        Finds the cover image of a comic.

        Returns:
            The filepath of the image file believed to be the cover.
        """
        if not self.image_names:
            raise ValueError("Empty file list")

        ranked: list[tuple[int, int, str]] = sorted(self.score(f) for f in self.image_names)
        return ranked[0][-1]
   
    def extract_image_bytes(self) -> None:
        cover_file_name = self.choose_cover()
        with zipfile.ZipFile(self.filepath, "r") as zf:
            with zf.open(cover_file_name) as img_file:
                self.cover_bytes = img_file.read()
 
    def save_cover(self, out_dir: str, primary_key: str) -> tuple[str, str]:
        """
        Saves two copies of the same image with different sizes
        and suffixes to their filename.

        Args:
            primary_key: The primary key id of the comic from the database.
            out_dir: The output directory.

        Returns:
            A tuple containing the file path of two images (smaller, bigger).
        """
        t_height = 400
        b_height = 800
        variants = {}
        with Image.open(BytesIO(self.cover_bytes)) as img:
            for name, height in [("thumbnail", t_height), ("browser", b_height)]:
                w, h = img.size
                new_w = int(w * (height / h))
                resized_img = img.resize((new_w, height), Image.Resampling.LANCZOS)
                
                if name == "thumbnail":
                    quality = 90
                else:
                    quality = 80

                buffer = BytesIO()
                resized_img.save(buffer, format="JPEG", quality=quality, optimize=True)
                variants[name] = buffer.getvalue()
        
        file_dict = {}
        for key, value in variants.items():
            if key == "thumbail":
                out_path_t = os.path.join(out_dir, f"{primary_key}_t.jpg")
                file_dict["thumbnail"] = (value, out_path_t)
            elif key == "browser":
                out_path_b = os.path.join(out_dir, f"{primary_key}_b.jpg")
                file_dict["browser"] = (value, out_path_b)
        
        for _, value in file_dict.items():
            with open(value[1], "wb") as f:
                f.write(value[0])
        
        return file_dict["thumbnail"][1], file_dict["browser"[1]]

    def find_credit_pages(self) -> Optional[str]:
        """
        Searches for comic ripper pages among the image files.
        Identifies comic ripper pages by filenames that are very different
        from the names of the first 40% of files.

        Raises:
            ValueError: if there are no images found in the archive on filepath.

        Returns the filepath of the supposed credit page or None if
        nothing is found.
        """
        if not self.image_names:
            raise ValueError("Empty archhve: no image files found.")
        
        self.image_names.sort()
        common_files_index = int(len(self.image_names) * 0.4)
        early_files = self.image_names[:common_files_index]
        file_paths_to_compare = random.sample(early_files, min(5, len(early_files)))
        last_files = self.image_names[-3:]
        not_matching_files = {
            j
            for j in last_files
            for k in file_paths_to_compare
            if Levenshtein.distance(j, k) > 10
        }

        if len(not_matching_files) == 1:
            return str(not_matching_files[0])
        else:
            return None


class MetadataInputting:
    def __init__(self, comicinfo_dict: ComicInfo) -> None:
        self.clean_info = comicinfo_dict
        self.db_ready_dict = None
    
    def build_dict(self) -> ComicInfo:
        final_dict: ComicInfo = {
            "title": self.clean_info["title"],
            "series": self.clean_info["series"]
        }

# ======================
# Database Inputting
# =======================


def build_dict(path: str) -> dict[str, Any]:
    """
    Builds a metadata dictionary for a comic archive from its ComicInfo.xml file.
    This data will eventually be pushed to database.

    Args:
        path: The filepath of the comic archive.

    Returns:
        A dictionary of metadata fields to be stored in the main comics table.

    Raises:
        ValueErrors: if parsing fails to find a corresponding match.
        KeyErrors: if data cannot be read.

    """
    dic = {
        "title": "",
        "series": "",
        "volume_id": "",
        "publisher_id": "",
        "release_date": "",
        "file_path": path,
        "description": "",
        "creators": "",
        "characters": "",
        "teams": ""
    }

    dic["description"] = parse_desc(path)

    probable_pub = parse_publisher(path)
    if probable_pub:
        try:
            dic["publisher_id"] = match_publisher(probable_pub)
        except KeyError as e:
            logging.warning(f"Publisher not matched: {e}")
            dic["publisher_id"] = 0
    else:
        dic["publisher_id"] = 0

    try:
        title, type_id = title_parsing(path)
        dic["title"] = title
        dic["series"] = title
        dic["coll_type_id"] = type_id
    except ValueError as e:
        logging.error(f"Title parsing failed: {e}")
        dic["title"] = "Unknown Title"
        dic["series"] = "Unknown Series"
        dic["coll_type_id"] = 0

    try:
        month = parse_month(path)
        year = parse_year(path)
        if month and year:
            dic["release_date"] = f"{month}/year"
        else:
            raise ValueError("Missing month/year")
    except Exception as e:
        logging.warning(f"Date parsing failed: {e}")
        dic["release_date"] = "01/2000"

    characters = parse_characters(path)
    dic["characters"] = characters if characters else ""

    teams = parse_teams(path)
    dic["teams"] = teams if teams else ""

    creators = parse_creators(path)
    dic["creators"] = creators if creators else ""

    return dic


def dic_into_db(my_dic: dict) -> None:
    """
    First checks to see if the input has any blank fields.
    If not it inputs them into the database.

    Args:
    my_dic: A metadata dictionary following the structure layed out in
    build_dic.
    """
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()

    for key, value in my_dic.items():
        if value is None:
            raise ValueError(f"Dictionary field '{key}' is None.")
            # Need to trigger another function or re-tag
        else:
            cursor.execute(
                """
                   INSERT INTO comics (title, series, volume_id, publisher_id,
                    release_date, file_path, front_cover_path, description)
                   VALUES (:title, :series, :volume_id, :pubslisher_id,
                   :release_date, :file_path, :front_cover_path, :description)
                   """,
                my_dic,
            )
    conn.commit()
    conn.close()
    return None


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

        try:
            self.process_file(filepath)
        except Exception as e:
            logging.error(f"Error processing file {filepath}: {e}")

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

    def process_file(self, path: str, dest_path_temp: str) -> None:
        """
        Moves the processed file to a target directory, renaming it if the file
        name is already taken.

        Args:
            path: Path to newly detected file to be moved.
            dest_path_temp: Target destination directory.
        """
        filename = os.path.basename(path)

        if os.path.exists(dest_path_temp):
            base, ext = os.path.splitext(filename)
            timestamp = int(time.time())
            new_filename = f"{base}_{timestamp}{ext}"
            dest_path = os.path.join("dir", new_filename)
            logging.warning(f"File exists, renaming to: {new_filename}")

        shutil.move(path, dest_path)
        logging.info(f"Moved file to library: {dest_path}")

    def handle_new_file(self, path: str) -> Optional[Tuple[int]]:
        """
        Handles newly deteced files by inserting them into the database
        and converting format if needed.

        Args:
            path: Path of the newly detected file.
        """
        if is_comic(path):
            if get_ext(path) == ".cbr":
                path = convert_cbz(path)

            conn = sqlite3.connect("comics.db")
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO comics (title, file_path)
                VALUES (?, ?)
            """,
                (get_name(path), path),
            )
            comic_id = cursor.lastrowid
            if comic_id:
                return (comic_id,)

            conn.commit()
            conn.close()

            if not has_metadata(path):
                pass  # This is where to call the tagging function

            # files that make to here are downloaded already with metadata,
            # if that is the case need to extract data
            # so should call another function here

        else:
            logging.critical("Wrong file type.")


obs = Observer()
obs.schedule(DownloadsHandler(), path_to_obs, recursive=False)
obs.start()
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    obs.stop()
    obs.join()

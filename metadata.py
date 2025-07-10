import logging
import os
import random
import re
import sqlite3
import defusedxml.ElementTree as ET
# import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from typing import Optional, Tuple, Union, Any, TypedDict
import tempfile

import Levenshtein
from fuzzywuzzy import fuzz
from PIL import Image
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from word2number import w2n

from file_utils import convert_cbz, get_ext, get_name, is_comic

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("log.txt")],
)


def find_credit_pages(path: str) -> Tuple[str, str]:
    """
    Searches for comic ripper pages among the image files.
    Identifies comic ripper pages by filenames that are very different
    from the names of the first 40% of files.

    Args:
        path: The filepath of the comic archive.

    Raises:
        ValueError: if there are no images found in the archive on filepath.

    Returns a tuple with first entry always the same path variable
    and second is either the name of the credit page or an empty string.
    """
    with zipfile.ZipFile(path, "r") as arch:
        image_files = [
            f for f in arch.namelist() if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]
        if not image_files:
            raise ValueError("Empty archive: no image files found.")

        image_files.sort()
        common_files_index = int(len(image_files) * 0.4)
        early_files = image_files[:common_files_index]
        file_paths_to_compare = random.sample(early_files, min(5, len(early_files)))
        last_files = image_files[-3:]
        not_matching_file = {
            j
            for j in last_files
            for k in file_paths_to_compare
            if Levenshtein.distance(j, k) > 10
        }
        if len(not_matching_file) == 1:
            return path, list(not_matching_file)[0]
        else:
            logging.info("No credit pages found!")
            return path, ""


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


def save_cover(id: int, bytes: bytes, out_dir: str = download_path) -> Tuple[str, str]:
    """
    Saves two copies of the same image with different sizes
    and suffixes to their filename.

    Args:
        id: The primary key id of the comic from the database.
        bytes: The raw data of the cover image.
        out_dir: The output directory.

    Returns:
        A tuple containing the file path of two images (smaller, bigger).
    """
    t_height = 400
    b_height = 800
    variants = {}
    with Image.open(BytesIO(bytes)) as img:
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

    file_dic = {}
    for key, value in variants.items():
        if key == "thumbnail":
            out_path_t = os.path.join(out_dir, (f"{id}_cover_t.jpg"))
            file_dic["thumbnail"] = (value, out_path_t)
        elif key == "browser":
            out_path_b = os.path.join(out_dir, (f"{id}_cover_b.jpg"))
            file_dic["browser"] = (value, out_path_b)

    for _key, value in file_dic.items():
        with open(value[1], "wb") as f:
            f.write(value[0])

    return file_dic["thumbnail"][1], file_dic["browser"][1]


def find_cover(path: str, out_dir: str) -> None:
    """
    Finds the cover image of a comic and saves two copies of different sizes
    of it to disk.

    Args:
        path: The filepath of the comic archive.
        out_dir: The filepath of the directory containing all the thumbnail images.
    """
    comicid = get_comicid_from_path(path)
    with zipfile.ZipFile(path, "r") as zip_ref:
        image_files = [
            f
            for f in zip_ref.namelist()
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]
        if not image_files:
            raise ValueError("Empty archive: no image files found.")
        cover_files = [
            f
            for f in image_files
            if os.path.splitext(os.path.basename(f))[0].lower() == "cover"
        ]
        if cover_files:
            first_image = zip_ref.read(cover_files[0])
        else:
            image_files.sort()
            first_image = zip_ref.read(image_files[0])
        save_cover(comicid, first_image, out_dir)


def find_metadata(path: str):
    """
    Extracts and parses the ComicInfo.xml metadata file from an archive.

    Args:
        path: The filepath of the comic archive file.

    Returns:
        The root element of the parsed ComicInfo.xml file.

    Raises:
        zipfile.BadZipFile: If the file is not a valid ZIP archive.
        FileNotFoundError: If the file is not found.
        KeyError: If ComicInfo.xml is not found in the archive.
        ET.ParseError: If ComicInfo.xml is not valid XML.
        Any other exceptions encountered during file access/parsing.
    """
    with zipfile.ZipFile(path, "r") as cbz:
        with cbz.open("ComicInfo.xml") as xml_file:
            tree = ET.parse(xml_file)
            return tree.getroot()


def get_text(root, tag: str) -> str:
    """
    Searches for results under the tag given. Returns the stripped lowercase content.

    Args:
        root: The base of the xml tree (where pretty much all the data is).
        tag: The section to search for (e.g. writer, summary etc).

    Returns:
        The lowercase, stripped text from the tag.

    Raises:
        KeyError: If the tag is missing or has no text content.
    """
    element = root.find(tag)
    if element is not None and element.text:
        return element.text.strip().lower()
    else:
        raise KeyError(f"No info inside tag: {tag}.")


def normalise_publisher(name: str) -> str:
    suffixes = ["comics", "publishing", "group", "press", "inc.", "inc", "llc"]
    tokens = name.replace("&", "and").split()
    return " ".join([t for t in tokens if t not in suffixes])


required_fields = ["Title", "Series", "Year", "Number"]


def has_metadata(path: str, required: list = required_fields) -> bool:
    """
    Checks that the required metadata fields are complete with some info
    e.g. that they are not blank.

    Args:
    path: The file path of the comic archive file.
    required: A list of the fields that must be present.

    Note:
    Will be used to remove None type option from easy_parse function
    """
    try:
        with zipfile.ZipFile(path, "r") as cbz:
            if "ComicInfo.xml" not in cbz.namelist():
                print(f"'ComicInfo.xml' not found in {path}")
                return False

            with cbz.open("ComicInfo.xml") as file:
                tree = ET.parse(file)
                root = tree.getroot()

                for field in required:
                    element = root.find(field)
                    if element is None or not element.text.strip():
                        logging.error(f"Field '{field}' is missing or blank.")
                        return False

        logging.debug("All required fields are present and not blank")
        return True

    except Exception as e:
        logging.error(f"Error occurred: {e}")
        return False


# =================================================
# Parsing the easy metadata which requires no logic
# =================================================


def easy_parse(path: str, field: str, as_type: type = str) -> Union[str, int]:
    """
    Returns metadata from the corresponding field by parsing an XML tree.
    Assumes ComicInfo.xml has already been verified to exist and be readable.

    Args:
    path: The filepath of the comic archive file.
    field: The name of the metadata field.
    as_type: The type that the metadata must be returned as.
            Required as all metadata fields are strings by default
            but some must be integers.

    Returns:
    The metadata inside that field, either a string or integer.
    Never type None.
    """
    root = find_metadata(path)

    text = get_text(root, field)

    if text is None:
        raise KeyError(f"Field '{field}' not found in metadata.")

    try:
        return as_type(text)
    except ValueError as e:
        raise TypeError(
            f"Could not convert field '{field}' to {as_type.__name__}"
        ) from e


def parse_desc(path: str) -> str:
    # Returns the summary or raises errors.
    return easy_parse(path, "Summary")


def parse_series(path: str) -> str:
    # Returns the series or raises errors.
    return easy_parse(path, "Series")


def parse_vol_num(path: str) -> int:
    # Returns the volume number or raises errors.
    return easy_parse(path, "Number", int)


def parse_year(path: str) -> int:
    # Returns the year or raises errors.
    return easy_parse(path, "Year", int)


def parse_month(path: str) -> int:
    # Returns the month or raises errors.
    return easy_parse(path, "Month", int)


def parse_publisher(path: str) -> str:
    # Returns the publisher or raises errors.
    return easy_parse(path, "Publisher")


def parse_title(path: str) -> str:
    # Returns the title or raises errors.
    return easy_parse(path, "Title")


def parse_creators(path: str, tag: str) -> set[str]:
    """
    Returns a list of the creators where each entry is a single creator.

    Args:
        path: The filepath of the comic archive to be parsed.
        tag: The job title of the creator(s) for example:
            'Writer' or 'Penciller'

    Returns:
        A list of names for all of the creators listed under a certain role.
    """
    creators = easy_parse(path, tag)
    return set(creators.split(", "))


def parse_characters(path: str) -> set[str]:
    characters = easy_parse(path, "Characters")
    return set(characters.split(", "))


def parse_teams(path: str) -> set[str]:
    teams = easy_parse(path, "Teams")
    return set(teams.split(", "))


# ===========================================
# Advanced parsing that requires extra logic
# ===========================================


def match_publisher(
    a: str,
) -> int:
    """
    Matches the natural language name of a publisher from metadata
    to an entry in the list of known publishers with numbered keys from the sql table.
    This uses fuzzy matches due to alterations of publisher names.

    Args:
        a: The string extracted from ComicInfo.xml to be matched.

    Returns:
        The ID of the best-matching known publisher.

    Raises:
        KeyError: If no known publisher matches closely enough.
    """
    known_publishers = [
        (1, "Marvel Comics"),
        (2, "DC Comics"),
        (3, "Image Comics"),
        (4, "Dark Horse Comics"),
        (5, "IDW Comics"),
        (6, "Valiant Comics"),
        (7, "2000AD Comics"),
    ]
    best_score = 0
    best_match = None
    normalised_pub = normalise_publisher(a)
    for pub_id, pub_name in known_publishers:
        score = fuzz.token_set_ratio(normalised_pub, normalise_publisher(pub_name))
        if score > best_score:
            best_score = score
            best_match = (pub_id, pub_name)
    if best_score >= 80 and best_match:
        return best_match[0]
    else:
        raise KeyError(f"Publisher {a} not known.")


# use Amazing Spider-Man Modern Era Epic Collection: Coming Home

# File Naming System: [Series_Name][Start_Year] -
# [Collection_Type] [Volume_Number] ([date in month/year])
# User Visible Title: [Series] [star_year] -
# [collection type] Volume [volume_number]: [Title] [month] [year]




def title_parsing(path: str) -> Tuple[str, int]:
    """
    Parses the title from the ComicInfo.xml to determine
    collection type and cleaned series title.

    Args:
        path: The filepath of the comic archive.

    Returns:
        A tuple off (clean_title, collection_type_id).

    Raises:
        ValueError: if the title or collection type cannot be determined.
    """
    title_raw = parse_title(path)
    if not title_raw:
        raise ValueError(f"Could not parse title from path: {path}")

    title_raw = title_raw.lower()
    title = parse_series(path)
    if not title:
        raise ValueError(f"Could not parse series from path: {path}")

    for keyword, type_id in series_overrides:
        if keyword in title_raw:
            cleaned_title = title_raw.replace(keyword, "").strip(" -:").title()
            return cleaned_title or title.title(), type_id

    match = re.search(
        r"(volume|book)\s*(\d+|one|two|three|four"
        "|five|six|seven|eight|nine|ten|eleven|twelve)",
        title_raw,
    )
    if match:
        try:
            cleaned_title = title_raw.replace(match.group(0), "").strip(" -:").title()
            return cleaned_title or title.title(), 1
        except ValueError:
            logging.warning(
                "Volume number couldn't be parsed; falling back to basic title."
            )
    return title.title(), 1


class ComicInfo(TypedDict):
    title: str
    series: str
    volume_num: int
    publisher: str
    month: int
    year: int
    filepath: str
    description: str
    creators: list[tuple]
    characters: list[str]
    teams: list[str]


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
  
    def has_complete_metadata(self, required: list = required_fields) -> bool:
        for field in required:
            try:
                self.get_text(field)
            except KeyError:
                return False
        return True           

    def get_text(self, tag: str) -> str:
        element = self.metadata_root.find(tag)
        if element is not None and element.text:
            return element.text.strip()
        else:
            raise KeyError(f"No info inside tag: {tag}.")
 
    def easy_parsing(self, field: str, as_type: type = str) -> str | int:
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
    def __init__(self, raw_dict: dict) -> None:
        self.raw_info = raw_dict
        self.title_info = None

    @staticmethod
    def normalise_publisher_name(name: str) -> str:
        suffixes = ["comics", "publishing", "group", "press", "inc.", "inc", "llc"]
        tokens = name.replace("&", "and").lower().split()
        return " ".join([t for t in tokens if t not in suffixes])
    
    @staticmethod
    def title_case(title: str) -> str:
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
                    issue_number = None

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


# class DownloadsHandler(FileSystemEventHandler):
#     """
#     Watches a directory for new files and processes them when they appear.

#     Attributes:
#         None

#     Methods:
#         on_created(event): Triggered when a file is created. Waits until file
#     is stable then processes it.
#         on_moved(event): Triggered when a file is moved. Handles processing
#     if moved to the watched folder.
#         on_deleted(event): Triggered when a file is deleted.
#         is_file_ready(filepath, stable_time, check_interval): Checks if a file has
#     stopped changing size to ensure it's fully written.
#         process_file(path, dest_path_temp): Moves a stable file to a destination,
#     renaming if needed.
#         handle_new_file(path): Inserts a new comic into the database and converts
#     formats if necessary.
#     """

#     def on_created(self, event: FileSystemEventHandler) -> None:
#         """
#         Called when a new file is created in the watched directory.

#         Args:
#             event(FileSystemEvent): The file system event triggered.
#         """
#         if event.is_directory:
#             return

#         filepath = event.src_path
#         filename = os.path.basename(filepath)

#         if filename.endswith(".part"):
#             logging.info(f"Ignoring partial file: {filename}")
#             return

#         logging.info(f"Detected new file: {filename}")

#         time.sleep(2)

#         if not self.is_file_ready(filepath):
#             logging.warning(f"File not stable yet: {filename}")
#             return

#         try:
#             self.process_file(filepath)
#         except Exception as e:
#             logging.error(f"Error processing file {filepath}: {e}")

#     def on_moved(self, event: FileSystemEventHandler) -> None:
#         """
#         Called when a file is moved.

#         Args:
#             event(FileSystemEvent): The file system move event.
#         """
#         if event.dest_path == path_to_obs:
#             if not event.is_directory:
#                 file_path = event.src_path
#                 logging.debug(f"New file detected: {file_path}")
#                 self.handle_new_file(file_path)

#     def on_deleted(self, event: FileSystemEventHandler) -> None:
#         """
#         Called when a file is deleted.

#         Args:
#             event (FileSystemEvent): The file system delete event.
#         """
#         logging.debug(f"Detected a file deletion: {event.src_path}")

#     def is_file_ready(
#         self, filepath: str, stable_time: int = 5, check_interval: int = 1
#     ) -> bool:
#         """
#         Checks to see if the file size has stabilised over time,
#         indicating it's fully written.

#         Args:
#             filepath: Path to newly detected file.
#             stable_time: Number of consectutive stable intervals.
#         intervals before confirming readiness.
#             check_interval: The number of seconds to wait between intervals.

#         Returns:
#             bool: True if file is stable and ready to be moved, False otherwise.
#         """
#         prev_size = -1
#         stab_counter = 0
#         while stab_counter < stable_time:
#             try:
#                 current_size = os.path.getsize(filepath)
#             except FileNotFoundError:
#                 logging.warning(f"File {filepath} disappeared.")
#                 return False

#             if current_size == prev_size:
#                 stab_counter += 1
#             else:
#                 stab_counter = 0
#                 prev_size = current_size

#             time.sleep(check_interval)

#         return True

#     def process_file(self, path: str, dest_path_temp: str) -> None:
#         """
#         Moves the processed file to a target directory, renaming it if the file
#         name is already taken.

#         Args:
#             path: Path to newly detected file to be moved.
#             dest_path_temp: Target destination directory.
#         """
#         filename = os.path.basename(path)

#         if os.path.exists(dest_path_temp):
#             base, ext = os.path.splitext(filename)
#             timestamp = int(time.time())
#             new_filename = f"{base}_{timestamp}{ext}"
#             dest_path = os.path.join("dir", new_filename)
#             logging.warning(f"File exists, renaming to: {new_filename}")

#         shutil.move(path, dest_path)
#         logging.info(f"Moved file to library: {dest_path}")

#     def handle_new_file(self, path: str) -> Optional[Tuple[int]]:
#         """
#         Handles newly deteced files by inserting them into the database
#         and converting format if needed.

#         Args:
#             path: Path of the newly detected file.
#         """
#         if is_comic(path):
#             if get_ext(path) == ".cbr":
#                 path = convert_cbz(path)

#             conn = sqlite3.connect("comics.db")
#             cursor = conn.cursor()
#             cursor.execute(
#                 """
#                 INSERT INTO comics (title, file_path)
#                 VALUES (?, ?)
#             """,
#                 (get_name(path), path),
#             )
#             comic_id = cursor.lastrowid
#             if comic_id:
#                 return (comic_id,)

#             conn.commit()
#             conn.close()

#             if not has_metadata(path):
#                 pass  # This is where to call the tagging function

#             # files that make to here are downloaded already with metadata,
#             # if that is the case need to extract data
#             # so should call another function here

#         else:
#             logging.critical("Wrong file type.")


# obs = Observer()
# obs.schedule(DownloadsHandler(), path_to_obs, recursive=False)
# obs.start()
# try:
#     while True:
#         time.sleep(1)
# except KeyboardInterrupt:
#     obs.stop()
#     obs.join()

import logging
import os
import random
import re
import shutil
import sqlite3
import time
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from typing import Optional, Tuple, Union

import Levenshtein
from fuzzywuzzy import fuzz
from PIL import Image
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from file_utils import convert_cbz, get_ext, get_name, is_comic

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("log.txt")],
)


def find_credit_pages(path: str) -> Tuple[str, str] | None:
    if get_ext(path) == ".cbz":
        with zipfile.ZipFile(path, "r") as arch:
            image_files = [
                f
                for f in arch.namelist()
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if not image_files:
                logging.error("Empty Archive.")
                return None
            image_files.sort(key=sort_imgs)
            common_files_index = int(len(image_files) * 0.4)
            early_files = image_files[:common_files_index]
            file_paths_to_compare = random.sample(early_files, min(5, len(early_files)))
            last_files = image_files[-3:]
            not_matching_file = set()
            for j in last_files:
                for k in file_paths_to_compare:
                    dist = Levenshtein.distance(j, k)
                    if dist > 10:
                        not_matching_file.add(j)
            not_matching_file_list = list(not_matching_file)
            if len(not_matching_file_list) == 1:
                return path, not_matching_file_list[0]
            else:
                logging.info("No credit pages found!")
                return None


def pad(n: int) -> str:
    return f"{n:04}" if n < 1000 else str(n)


def sort_imgs(filename: str) -> Optional[int]:
    numbers = re.findall(r"\d+", filename)
    return int(numbers[-1]) if numbers else -1


def get_comicid_from_path(
    path: str,
) -> Optional[int]:
    # Takes a file path as an argument and returns the primary key id

    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM comics WHERE path = {}".format(path))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    else:
        logging.error("Could not find reference to file path in database.")
        return None


download_path = os.getenv("DEST_FILE_PATH")


def save_cover(id: int, bytes: bytes, out_dir: str = download_path) -> Tuple[str, str]:
    """
    Saves two copies of the same image with different sizes.

    Parameters:
    id (int): The primary key id of the comic.
    bytes (bytes): The raw data of the cover image.
    out_dir (str): The output directory.

    Returns:
    tuple: A tuple containing the file path of two images (smaller, bigger).
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


def find_cover(path: str) -> Optional[None]:
    """
    Finds the cover image of a comic and saves two copies
    of it and puts their file paths to the database.

    Parameter:
    path (str): The file path of the comic
    """
    if get_ext(path) == ".cbz":
        with zipfile.ZipFile(path, "r") as zip_ref:
            image_files = [
                f
                for f in zip_ref.namelist()
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if not image_files:
                logging.error("Empty archive.")
                return
            cover_files = [
                f
                for f in image_files
                if os.path.splitext(os.path.basename(f))[0].lower() == "cover"
            ]
            if cover_files:
                first_image = zip_ref.read(cover_files[0])
            else:
                image_files.sort(key=sort_imgs)
                first_image = zip_ref.read(image_files[0])
        out = save_cover(path, first_image)
        # Need to make another column to store paths for both cover image sizes
        # Need to move the database logic elsewhere.
        conn = sqlite3.connect("comics.db")
        cursor = conn.cursor()
        cursor.execute(
            f""" UPDATE comics
                        SET front_cover_path_t = {out[0]},
                        front_cover_path_b = {out[1]}
                        WHERE id = {get_comicid_from_path(path)}
                    """
        )
        conn.commit()
        conn.close()

    else:
        logging.error("Need to convert to cbz first!")
        return


def find_metadata(path: str) -> ET.Element:
    try:
        with zipfile.ZipFile(path, "r") as cbz:
            cbz.getinfo("ComicInfo.xml")
            with cbz.open("ComicInfo.xml") as xml_file:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                return (root, None)
    except zipfile.BadZipFile:
        return (None, "Not a valid CBZ/ZIP file.")
    except FileNotFoundError:
        return (None, "File not found.")
    except Exception as e:
        return (None, f"Unexpected error: {e}")


def get_text(root, tag: str) -> Optional[str]:
    element = root.find(tag)
    if element is not None and element.text:
        return element.text.strip().lower()
    else:
        logging.error("No metadata under {tag} tag.")


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
    root, _ = find_metadata(path)
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


def parse_creator(path: str, tag: str) -> list[str]:
    """
    Returns a list of the creators where each entry is a single creator.

    Args:
    path: The filepath of the comic archive to be parsed.
    tag: The job title of the creator(s) for example:
        'Writer' or 'Penciller'
    """
    creators = easy_parse(path, tag)
    return creators.split(", ")


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
    for pub_id, pub_name in known_publishers:
        score = fuzz.token_set_ratio(
            normalise_publisher(a), normalise_publisher(pub_name)
        )
        if score > best_score:
            best_score = score
            best_match = (pub_id, pub_name)
    if best_score >= 80:
        return best_match[0]
    else:
        raise KeyError(f"Publisher {best_match[0]} not known.")


# use Amazing Spider-Man Modern Era Epic Collection: Coming Home

# File Naming System: [Series_Name][Start_Year] -
# [Collection_Type] [Volume_Number] ([date in month/year])
# User Visible Title: [Series] [star_year] -
# [collection type] Volume [volume_number]: [Title] [month] [year]


series_overrides = [
    ("tpb", 1),
    ("omnibus", 2),
    ("epic collection", 3),
    ("modern era epic collection", 4),
]


def title_parsing(path) -> Optional[Tuple[str, int]]:
    common_titles = {"volume", "book", "collection"}
    coll_type = None
    override = False
    title_raw = parse_title(path)
    match = re.fullmatch(
        r"""^volume\s*(\d+|one|two|three|four|five|six|seven|eight|
        nine|ten|eleven|twelve|thirteen|fourteen|fifteen)$""",
        title_raw if title_raw is not None else "",
    )
    if common_titles in path:
        # Need logic here
        return None
    if match:
        title = parse_series(path)
        # vol = match.group(1)
        # if vol.isdigit():
        #     vol_num = int(vol)
        # else:
        #     vol_num = int(w2n.word_to_num(vol))
        # need to deal with vol_num being None
    # need to deal with 'volume being in the title
    if title is None:
        logging.error("No title found.")
        return None
    for f in series_overrides:
        if f[0] in title:
            title = title.replace(f[0], "")
            override = True
            coll_type = f[1]
        if coll_type is None:
            pass
        # Need to add a function to identify type
        elif override is False:
            logging.error("No usuable title, need user input.")
        # Need to do something here to fix if no title can be found


def build_dict(path) -> Optional[dict]:
    dic = dict.fromkeys(
        [
            "title",
            "series",
            "volume_id",
            "publisher_id",
            "release_date",
            "file_path",
            "front_cover_path",
            "description",
        ]
    )
    dic["description"] = parse_desc(path)
    dic["file_path"] = f"{path}"
    probable_pub = parse_publisher(path)
    if probable_pub:
        dic["publisher_id"] = match_publisher(probable_pub)
    else:
        dic["publisher_id"] = None
    dic["release_date"] = f"{parse_month(path)}/{parse_year(path)}"
    return dic


def dic_into_db(my_dic) -> None:
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()
    # ready_or_not = True
    for value in my_dic:
        if value is None:
            logging.warning(
                "Missing some information"
            )  # Need to trigger another function or re-tag
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


# Watchdog stuff:

path_to_obs = os.getenv("PATH_TO_WATCH")


class DownloadsHandler(FileSystemEventHandler):

    def on_created(self, event):
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

    def on_moved(self, event):
        if event.dest_path == path_to_obs:
            if not event.is_directory:
                file_path = event.src_path
                logging.debug(f"New file detected: {file_path}")
                self.handle_new_file(file_path)
        else:
            pass

    def on_deleted(self, event):
        logging.debug(f"Detected a file deletion: {event.src_path}")

    def is_file_ready(self, filepath, stable_time=5, check_interval=1):
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

    def process_file(self, path, dest_path_temp):
        filename = os.path.basename(path)

        if os.path.exists(dest_path_temp):
            base, ext = os.path.splitext(filename)
            timestamp = int(time.time())
            new_filename = f"{base}_{timestamp}{ext}"
            dest_path = os.path.join("dir", new_filename)
            logging.warning(f"File exists, renaming to: {new_filename}")

        shutil.move(path, dest_path)
        logging.info(f"Moved file to library: {dest_path}")

    def handle_new_file(self, path):
        if is_comic(path):
            if get_ext(path) == ".cbr":
                path = convert_cbz(path)

            conn = sqlite3.connect("comics.db")
            cursor = conn.cursor()
            cursor.execute(
                f"""
                INSERT INTO comics (title, file_path)
                VALUES ({get_name(path)}, {path})
                            """
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

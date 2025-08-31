import calendar
import os
import re
import xml.etree.ElementTree as ET  # nosec
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from difflib import SequenceMatcher
from enum import Enum, IntEnum, auto
from io import BytesIO
from pathlib import Path
from typing import Callable, Optional, Protocol

import imagehash
import requests
from dotenv import load_dotenv
from fuzzywuzzy import fuzz
from PIL import Image

from comic_match_logic import ResultsFilter
from classes.helper_classes import ComicInfo
from metadata_cleaning import MetadataProcessing

load_dotenv()
API_KEY = os.getenv("API_KEY")
# ==================================
#   Filename Lexing
# ==================================


class MatchCode(IntEnum):
    NO_MATCH = 0
    ONE_MATCH = 1
    MULTIPLE_MATCHES = 2


def is_numeric_or_number_punctuation(x: str) -> bool:
    digits = "0123456789.,"
    return x.isnumeric() or x in digits


class QMode(Enum):
    COMBO = auto()
    SERIES = auto()
    TITLE = auto()


class ItemType(Enum):
    Error = auto()
    EOF = auto()
    Text = auto()
    LeftParen = auto()
    Number = auto()
    IssueNumber = auto()
    VolumeNumber = auto()
    RightParen = auto()
    Space = auto()
    Dot = auto()
    LeftBrace = auto()
    RightBrace = auto()
    LeftSBrace = auto()
    RightSBrace = auto()
    Symbol = auto()
    Skip = auto()
    Operator = auto()
    Calendar = auto()
    InfoSpecifier = auto()
    Honorific = auto()
    ArchiveType = auto()
    Publisher = auto()
    Keywords = auto()
    Author = auto()
    FCBD = auto()
    ComicType = auto()
    CollectionType = auto()
    C2C = auto()
    Separator = auto()


braces = [
    ItemType.LeftBrace,
    ItemType.LeftParen,
    ItemType.LeftSBrace,
    ItemType.RightBrace,
    ItemType.RightParen,
    ItemType.RightSBrace,
]

eof = chr(0)

key = {
    "fcbd": ItemType.FCBD,
    "freecomicbookday": ItemType.FCBD,
    "cbr": ItemType.ArchiveType,
    "cbz": ItemType.ArchiveType,
    "rar": ItemType.ArchiveType,
    "zip": ItemType.ArchiveType,
    "annual": ItemType.ComicType,
    "of": ItemType.InfoSpecifier,
    "dc": ItemType.Publisher,
    "marvel": ItemType.Publisher,
    "covers": ItemType.InfoSpecifier,
    "c2c": ItemType.C2C,
}


class Item:

    def __init__(self, typ: ItemType, pos: int, val: str) -> None:
        """
        Creates a new item which has been found in the string.

        Parameters:
        typ [ItemType] = The type defined above e.g. text or parenthesis.
        pos [int] = The position of the first character in the item.
        val [str] = The string representation of the token extracted
        """
        self.typ: ItemType = typ
        self.pos: int = pos
        self.val: str = val
        self.no_space = False

    def __repr__(self) -> str:
        return f"{self.val}: index: {self.pos}: {self.typ}"


class LexerFunc(Protocol):

    def __call__(self, __origin: "Lexer") -> "LexerFunc | None":
        pass


class Lexer:

    def __init__(
        self, string: str, *, allow_issue_start_with_letter: bool = False
    ) -> None:
        self.input: str = string
        self.state: LexerFunc | None = None
        self.pos: int = -1
        self.start: int = 0
        self.last_pos: int = 0
        self.paren_depth: int = 0
        self.brace_depth: int = 0
        self.sbrace_depth: int = 0
        self.items: list[Item] = []
        self.allow_issue_start_with_letter = allow_issue_start_with_letter

    def get(self) -> str:
        """
        Gets the next character in the string or returns end of string message
        and adds 1 to position counter.

        Parameters:
        self = the filemame to be lexed

        Returns:
        str = the next character in the filename
        or the null character to indicate end of string.
        """
        if int(self.pos) >= len(self.input) - 1:
            self.pos += 1
            return eof

        self.pos += 1
        return self.input[self.pos]

    def peek(self) -> str:
        """
        Looks at the next character in the string but does not 'consume' it.

        Will be used to 'look' at next character and decide what to do.

        Parameters:
        self = the filename to be lexed.

        Return:
        str = the next character in the string.

        """
        if int(self.pos) >= len(self.input) - 1:
            return eof
        return self.input[self.pos + 1]

    def backup(self) -> None:
        # Decreases the position by one, i.e.
        # goes back one character in the string.
        self.pos -= 1

    def emit(self, t: ItemType) -> None:
        """
        Adds the newly found token to the list of tokens and
        updates the start variable ready for the next token.

        Parameters:
        t [ItemType] = the kind of token to be added to the list.

        """
        self.items.append(Item(t, self.start, self.input[self.start : self.pos + 1]))
        self.start = self.pos + 1

    def ignore(self) -> None:
        # Ignores anything from the start position until
        # the current position, used to omit whitespaces etc.
        self.start = self.pos

    def accept(self, valid: str | Callable[[str], bool]) -> bool:
        """
        Checks to see if the next character in the lexer instance
        is in a certain string or is a certain type of character.

        Parameter:
        valid [str] = A string to see if the next character
        in the class instance is a substring of valid
        OR
        valid [Callable] = A function (e.g. isdigit ) that checks if
        the next character returns a truthy value

        Returns:
        bool = Whether or not the next character in the class
        instance is in the input string or function
        """
        if isinstance(valid, str):
            if self.get() in valid:
                return True

        else:
            if valid(self.get()):
                return True

        self.backup()
        return False

    def accept_run(self, valid: str | Callable[[str], bool]) -> bool:
        """
        Tries to accept a sequence of characters
        that are of the same type/token.

        Parameters:
        valid [str] = A string to see if the next character
        in the class instance is a substring of valid
        OR
        valid [Callable] = A function (e.g. isdigit ) that checks
        if the next character returns a truthy value

        Returns:
        bool = Returns whether the position actually moved forward
        or not, so you can consume entire tokens at a time.
        """
        initial = self.pos
        if isinstance(valid, str):
            while self.get() in valid:
                continue
        else:
            while valid(self.get()):
                continue

        self.backup()
        return initial != self.pos

    def scan_number(self) -> bool:
        """
        Checks if a string is numeric and if it has a suffix
        of letters directly after, no whitespace.
        """
        if not self.accept_run(is_numeric_or_number_punctuation):
            return False
        if self.input[self.pos] == ".":
            self.backup()
        self.accept_run(str.isalpha)
        return True

    def run(self) -> None:
        # Keeps the lexer process running
        self.state = run_lexer
        while self.state is not None:
            self.state = self.state(self)


def errorf(lex: Lexer, message: str) -> None:
    lex.items.append(Item(ItemType.Error, lex.start, message))


def run_lexer(lex: Lexer) -> Optional[LexerFunc]:
    r = lex.get()

    if r == eof:
        lex.emit(ItemType.EOF)
        return None

    elif r.isspace():
        lex.ignore()
        return run_lexer

    elif r.isnumeric():
        lex.backup()
        return lex_number

    elif r == "#":
        if lex.peek().isnumeric():
            return lex_issue_number
        else:
            errorf(lex, "expected number after #")
            return run_lexer

    elif r.lower() == "v":
        if lex.peek().lower() == "o":
            lex.get()  # consume 'o'
        if lex.peek().lower() == "l":
            lex.get()  # consume 'l'
            if lex.peek() == ".":
                lex.get()  # consume '.'
            return lex_volume_number_full
        elif lex.peek().isdigit():
            return lex_volume_number
        else:
            return lex_text

    elif r.lower() == "b":
        lex.backup()
        if lex.input[lex.pos : lex.pos + 3].lower() == "by ":
            lex.start = lex.pos
            lex.pos += 2
            lex.emit(ItemType.InfoSpecifier)
            return lex_author
        lex.get()
        return lex_text

    elif r.lower() in "tophc":
        lex.backup()
        return lex_collection_type

    elif is_alpha_numeric(r):
        lex.backup()
        return lex_text

    elif r == "-":
        lex.emit(ItemType.Separator)
        return run_lexer

    elif r == "(":
        lex.emit(ItemType.LeftParen)
        lex.paren_depth += 1
        return run_lexer

    elif r == ")":
        lex.emit(ItemType.RightParen)
        lex.paren_depth -= 1
        if lex.paren_depth < 0:
            errorf(lex, "unexpected right paren " + r)
            return None
        return run_lexer

    elif r == "{":
        lex.emit(ItemType.LeftBrace)
        lex.brace_depth += 1
        return run_lexer

    elif r == "}":
        lex.emit(ItemType.RightBrace)
        lex.brace_depth -= 1
        if lex.brace_depth < 0:
            errorf(lex, "unexpected right brace " + r)
            return None
        return run_lexer

    elif r == "[":
        lex.emit(ItemType.LeftSBrace)
        lex.sbrace_depth += 1
        return run_lexer

    elif r == "]":
        lex.emit(ItemType.RightSBrace)
        lex.sbrace_depth -= 1
        if lex.sbrace_depth < 0:
            errorf(lex, "unexpected right square brace")
            return None
        return run_lexer
    else:
        errorf(lex, f"unexpected character: {r}")
        return run_lexer


def lex_space(lex: Lexer) -> LexerFunc:
    if lex.accept_run(is_space):
        lex.emit(ItemType.Space)
    return run_lexer


def lex_text(lex: Lexer) -> LexerFunc:
    while True:
        r = lex.get()

        if is_alpha_numeric(r) or r == "'":
            continue
        else:
            lex.backup()
            break
    word = lex.input[lex.start : lex.pos]

    lower_word = word.casefold()
    if lower_word in key:
        token_type = key[lower_word]
        if token_type in (ItemType.Honorific, ItemType.InfoSpecifier):
            lex.accept(".")
        lex.emit(token_type)
    elif cal(word):
        lex.emit(ItemType.Calendar)
    else:
        lex.emit(ItemType.Text)
    return run_lexer


def lex_number(lex: Lexer) -> LexerFunc | None:
    # Attempt to scan number from current position
    if not lex.scan_number():
        errorf(lex, "bad number syntax: " + lex.input[lex.start : lex.pos])
        return run_lexer

    # Handle ordinal or letter suffixes (e.g. '80th' or '20s')
    if lex.pos < len(lex.input) and lex.input[lex.pos].isalpha():
        lex.accept_run(str.isalpha)
        lex.emit(ItemType.Text)
        return run_lexer
    lex.emit(ItemType.Number)
    return run_lexer


def lex_issue_number(lex: Lexer) -> LexerFunc:
    # Only called when lex.input[lex.start] == "#"
    if not lex.peek().isnumeric():
        lex.emit(ItemType.Symbol)
        return run_lexer

    lex.accept_run(str.isdigit)

    lex.accept_run(str.isalpha)

    lex.emit(ItemType.IssueNumber)
    return run_lexer


def lex_author(lex: Lexer) -> LexerFunc:
    lex.accept_run(str.isspace)
    name_parts = 0

    while name_parts < 3:
        word_start = lex.pos
        lex.accept_run(str.isalpha)

        word = lex.input[word_start : lex.pos]

        if lex.peek() == ".":
            lex.get()
            word += "."
        if word and (word[0].isupper() or (len(word) == 2 and word[1] == ".")):
            name_parts += 1
        else:
            lex.pos = word_start
            break

        if not lex.accept(" "):
            break

    if name_parts >= 1:
        lex.emit(ItemType.Author)
    else:
        lex.emit(ItemType.Text)

    return run_lexer


def lex_collection_type(lex: Lexer) -> LexerFunc:
    lex.accept_run(str.isalpha)
    word = lex.input[lex.start : lex.pos].casefold()

    known_collections = {
        "tpb",
        "hc",
        "hardcover",
        "omnibus",
        "deluxe",
        "compendium",
        "digest",
    }

    if word in known_collections:
        lex.emit(ItemType.CollectionType)
    else:
        lex.emit(ItemType.Text)

    return run_lexer


def lex_volume_number(lex: Lexer) -> LexerFunc:
    lex.accept_run(str.isdigit)

    if lex.pos == lex.start:
        lex.accept_run(is_space)
        lex.accept_run(str.isdigit)

    if lex.pos > lex.start:
        lex.emit(ItemType.VolumeNumber)
    else:
        lex.emit(ItemType.Text)

    return run_lexer


def lex_volume_number_full(lex: Lexer) -> LexerFunc:
    lex.accept_run(is_space)
    if lex.peek().isdigit():
        lex.accept_run(str.isdigit)
        lex.emit(ItemType.VolumeNumber)
    # if lex.pos > lex.start:
    #     lex.emit(ItemType.VolumeNumber)
    else:
        lex.emit(ItemType.Text)

    return run_lexer


def is_space(character: str) -> bool:
    return character.isspace() or character == "_"


def is_alpha_numeric(character: str) -> bool:
    return character.isalpha() or character.isnumeric()


def cal(word: str) -> bool:
    word_lower = word.lower()

    months = [m.lower() for m in calendar.month_name if m] + [
        m.lower() for m in calendar.month_abbr if m
    ]
    if word_lower in months:
        return True

    return bool(re.fullmatch(r"\d{4}", word) or re.fullmatch(r"\d{4}s", word))


def lex(filename: str) -> Lexer:
    lex = Lexer(os.path.basename(filename))
    lex.run()
    return lex


class Parser:
    def __init__(self, list_of_tokens: list[Item]):
        self.tokens: list[Item] = list_of_tokens
        self.metadata: dict[str, str | int] = {}
        self.buffer: list[str] = []

    def construct_metadata(self) -> dict[str, str | int]:
        capture_title = False
        title_parts = []
        i = 0
        while i < len(self.tokens):
            item = self.tokens[i]

            if item.typ == ItemType.Text and not capture_title:
                self.buffer.append(item.val)

            elif item.typ == ItemType.CollectionType:
                self.metadata["collection_type"] = item.val

            elif item.typ == ItemType.IssueNumber:
                try:
                    self.metadata["issue"] = int(item.val.lstrip("#"))
                    capture_title = True
                except ValueError:
                    pass

            elif item.typ == ItemType.VolumeNumber:
                volume = int(re.findall(r"\d+", item.val)[0])
                self.metadata["volume"] = volume
                capture_title = True

            elif capture_title:
                if item.typ == ItemType.Text:
                    title_parts.append(item.val)
                elif item.typ == ItemType.Number:
                    if 1900 <= int(item.val):
                        self.metadata["year"] = int(item.val)
                        break

            elif item.typ == ItemType.Number and 1900 <= int(item.val):
                self.metadata["year"] = int(item.val)
                break

            i += 1

        if self.buffer:
            tokens = " ".join(self.buffer).split()
            self.metadata["series"] = " ".join(tokens)

        if title_parts:
            title = " ".join(title_parts).strip().lstrip("-").strip()
            if title:
                self.metadata["title"] = " ".join(title.split())

        return self.metadata


class RequestData:

    def __init__(
        self,
        issue_num: int,
        year: int,
        series: str,
        title: str,
        publisher: str | None = None,
    ):
        self.series = series
        self.title = title
        self.unclean_title = (series or "") + (title or "")
        self.num = issue_num
        self.pub_year = year
        self.publisher = publisher or ""


header = {
    "User-Agent": "AutoComicLibrary/1.0 (contact: adam.perrott@protonmail.com;"
    " github.com/CloakedLeader/comic_library)",
    "Accept": r"*/*",
    "Accept-Encoding": "gzip,deflate,br",
    "Connection": "keep-alive",
}
session = requests.Session()
session.headers.update(header)


class HttpRequest:

    base_address = "https://comicvine.gamespot.com/api"

    def __init__(self, data: RequestData, api_key: str):
        self.data = data
        self.api_key = api_key
        self.payload = self.create_info_dict(self.data.unclean_title)

    def create_info_dict(self, query):
        payload = {}
        payload["api_key"] = self.api_key
        payload["resources"] = "volume"
        payload["field_list"] = (
            "id,image,publisher,name,start_year,date_added,"
            "count_of_issues,description,last_issue"
        )
        payload["format"] = "json"
        payload["limit"] = 50
        return payload

    def build_url_search(self, query: str):
        payload = self.payload.copy()
        payload["query"] = query
        req = requests.Request(
            method="GET",
            url=f"{HttpRequest.base_address}/search/",
            params=payload,
            headers=header,
        )
        prepared = req.prepare()
        self.url_search = prepared.url
        print(self.url_search)

    def build_url_iss(self, id: int):
        req = requests.Request(
            method="GET",
            url=f"{HttpRequest.base_address}/issues/",
            params={
                "api_key": self.api_key,
                "format": "json",
                "filter": f"volume:{id}",
            },
        )
        prepared = req.prepare()
        self.url_iss = prepared.url
        print(self.url_iss)

    def get_request(self, type: str):
        if type == "search":
            if not hasattr(self, "url_search"):
                raise RuntimeError("You must build url before sending request.")
            if self.url_search is None:
                raise ValueError("search url cannot be None")
            response = session.get(self.url_search)
            if response.status_code != 200:
                print(
                    f"Request failed with status code: \
                      {response.status_code}"
                )
                print(response.text)
            data = response.json()

        elif type == "iss":
            if not hasattr(self, "url_iss"):
                raise RuntimeError("You must build url before sending request.")
            if self.url_iss is None:
                raise ValueError("issue url cannot be None")
            response = session.get(self.url_iss)
            if response.status_code != 200:
                print(
                    f"Request failed with status code: \
                      {response.status_code}"
                )
                print(response.text)
            data = response.json()

        else:
            print("Need to specify which database to search in.")
        if data["error"] != "OK":
            print("Error, please investigate")
            return
        # Want to tell the user to manually tag the comic.
        return data

    def download_img(self, url):
        try:
            response = requests.get(url, timeout=3000)
            response.raise_for_status()
            image = BytesIO(response.content)
            return image
        except Exception as e:
            print(f"Failed to process {url}: {e}")
            return None


class ResponseValidator:

    issue_threshold = 70
    volume_threshold = 50

    def __init__(self, response: dict, expected_data: RequestData):
        self.results = response["results"]
        self.expected_info = expected_data

    def filter_results(self, predicate):
        return [item for item in self.results if predicate(item)]

    def year_checker(self):
        def check_year(item):
            year = int(item["date_added"][:4])
            return abs(year - self.expected_info.pub_year) <= 4

        return self.filter_results(check_year)

    @staticmethod
    def fuzzy_match(a, b, threshold=65):
        return fuzz.token_sort_ratio(a, b) >= threshold

    def pick_best_volumes(self, number: int = 5):
        def score_name(item):
            score = 0.0
            name = item["name"]
            if name:
                score += SequenceMatcher(
                    None, name.lower(), self.expected_info.series.lower()
                ).ratio()
            return score

        scored_volumes = [(i, score_name(item)) for i, item in enumerate(self.results)]
        scored_volumes.sort(key=lambda x: x[1], reverse=True)
        top_indices = [i for i, _ in scored_volumes[:number]]
        return [self.results[i] for i in top_indices]

    def title_checker(self):
        def check_title(item):
            used_fallback = False
            ambig_names = ["tpb", "hc", "omnibus"]
            ambig_regexes = [
                r"^vol(?:ume)?\.?\s*\d+$",  # matches "vol.", "volume", "vol"
                r"^#\d+$",  # matches "#1", "#12" etc
                r"^issue\s*\d+$",  # matches "issue 3"
                r"\bvol(?:ume)?\.?\s*(one|two|three|four|\d+|i{1,3}|iv|v)\b",
                r"\bbook\s*(one|two|three|four|\d+|i{1,3}|iv|v)\b",
            ]
            title = item["name"]
            if title:
                lowered_title = title.lower().strip()
                is_ambig = lowered_title in ambig_names or any(
                    re.match(p, lowered_title) for p in ambig_regexes
                )
                if is_ambig:
                    title = item.get("volume", {}).get("name")
                    used_fallback = True
            else:
                title = item.get("volume", {}).get("name")
                used_fallback = True
            if title is None:
                return False
            threshold = (
                ResponseValidator.volume_threshold
                if used_fallback
                else ResponseValidator.issue_threshold
            )
            return self.fuzzy_match(
                title, self.expected_info.unclean_title, threshold=threshold
            )

        return self.filter_results(check_title)

    def pub_checker(self, results: list):
        foriegn_keywords = {
            "panini",
            "verlag",
            "norma",
            "televisa",
            "planeta",
            "deagostini",
            "urban",
        }
        english_publishers = {
            "Marvel": 31,
            "DC Comics": 10,
            "Image": 513,
            "IDW Publishing": 1190,
            "Dark Horse Comics": 364,
        }

        filtered = []
        for result in results:
            pub_dict = result["publisher"]
            pub_id = pub_dict["id"]
            pub_name = pub_dict["name"]
            if pub_id in english_publishers.values():
                filtered.append(result)
            elif any(word.lower() in foriegn_keywords for word in pub_name.split()):
                print(f"Filtered out {pub_name} due to foreign publisher.")
            else:
                filtered.append(result)
                print(f"Accepted '{pub_name}' but please check.")
        return filtered

    def issue_count_filter(self, limit: int = 12):
        def is_collection(item):
            issue_count = item["count_of_issues"]
            return True if issue_count < limit else False

        return self.filter_results(is_collection)

    def cover_img_url_getter(self, filtered_results):
        self.urls = []
        for i in filtered_results:
            self.urls.append(i["image"]["thumb_url"])

    def cover_img_comparison(
        self, known_image_hash, unsure_image_bytes, threshold=8
    ) -> bool:  # Returns true if it finds match.
        unsure_image = Image.open(unsure_image_bytes)
        hash1 = known_image_hash
        hash2 = imagehash.phash(unsure_image)
        hash_diff = hash1 - hash2
        print(
            f"[DEBUG] Hashing distance = \
              {hash_diff}, threshold = {threshold}"
        )
        return hash_diff <= threshold

    def cover_img_comp_w_weight(
        self, known_image_hashes, unsure_image_bytes, max_dist=64
    ):
        weights = {"phash": 0.6, "dhash": 0.2, "ahash": 0.2}
        unsure_hashes = {
            "phash": imagehash.phash(unsure_image_bytes),
            "dhash": imagehash.dhash(unsure_image_bytes),
            "ahash": imagehash.average_hash(unsure_image_bytes),
        }
        score = 0.0
        for key in weights:
            dist = known_image_hashes[key] - unsure_hashes[key]
            normalised = 1 - (dist / max_dist)
            score += weights[key] * normalised
        return score


class TaggingPipeline:
    def __init__(self, data: RequestData, path: str, size: float, api_key: str) -> None:
        self.data = data
        self.path = path
        self.size = size
        self.http = HttpRequest(data, api_key)
        self.validator = None
        self.cover = self.cover_getter()
        self.coverhashes = self.cover_hasher()
        # dictionary of (phash, dhash, ahash)
        self.results: list[dict] = []

    def cover_getter(self):
        with zipfile.ZipFile(self.path, "r") as zip_ref:
            image_files = [
                f
                for f in zip_ref.namelist()
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if not image_files:
                print("Empty archive.")
                return
            image_files.sort()
            cover = zip_ref.read(image_files[0])
            return BytesIO(cover)

    def cover_hasher(self):
        image = Image.open(self.cover)
        return {
            "phash": imagehash.phash(image),
            "dhash": imagehash.dhash(image),
            "ahash": imagehash.average_hash(image),
        }

    def run(self):
        queries = [
            f"{self.data.series} {self.data.title or ''}".strip(),
            self.data.series,
            self.data.title,
        ]
        potential_results = []

        skipped_vols = []
        for q in queries:
            good_matches = []

            self.http.build_url_search(q)
            results = self.http.get_request("search")
            self.validator = ResponseValidator(results, self.data)

            print(f"There are {len(results['results'])} results returned.")
            results = self.validator.issue_count_filter()
            self.validator.results = results
            results = self.validator.pick_best_volumes(number=8)
            self.validator.results = results
            results = self.validator.pub_checker(results)
            self.validator.results = results
            print(
                "After filtering for title, publisher and issue "
                + f"there are {len(results)} remaining results."
            )
            final_results = results

            if len(final_results) == 0:
                continue

            vol_info = []
            for i in final_results:
                id = i["id"]
                name = i["name"]
                vol_info.append((id, name))
            for index, (j, k) in enumerate(vol_info):
                self.http.build_url_iss(j)
                temp_results = self.http.get_request("iss")

                self.temp_validator = ResponseValidator(temp_results, self.data)
                print(
                    f"There are {len(self.temp_validator.results)}"
                    + f" issues in the matching volume: '{k}'."
                )
                temp_results = self.temp_validator.year_checker()
                self.temp_validator.results = temp_results
                temp_results = self.temp_validator.title_checker()
                self.temp_validator.results = temp_results

                print(
                    "After filtering for title and year "
                    + f"there are {len(temp_results)} results remaining."
                )
                if len(temp_results) != 0:
                    if len(temp_results) > 25:
                        print(
                            "Too many issues to compare covers, "
                            + f"skipping volume '{k}'."
                        )
                        skipped_vols.append((j, k, len(temp_results)))
                        continue
                    potential_results.extend(temp_results)
                    self.temp_validator.cover_img_url_getter(temp_results)
                    images = []
                    with ThreadPoolExecutor(max_workers=5) as executor:
                        images = list(
                            executor.map(
                                self.http.download_img, self.temp_validator.urls
                            )
                        )
                    matches_indices = []
                    for index, i in enumerate(images):
                        if i is None:
                            continue
                        try:
                            img_pil = Image.open(i)
                            score = self.temp_validator.cover_img_comp_w_weight(
                                self.coverhashes, img_pil
                            )
                            print(f"Index {index}: similarity score = {score:.2f}")
                            if score > 0.85:
                                matches_indices.append(index)
                        except Exception as e:
                            print(f"Error comparing image at index {index}: {e}.")
                    final_results = [temp_results[i] for i in matches_indices]
                    good_matches.extend(final_results)
                else:
                    continue

            if len(good_matches) == 1:
                print(good_matches[0]["volume"]["name"])
                print("There is ONE match!!!")
                print(good_matches)
                self.results.append(good_matches)
                return MatchCode.ONE_MATCH
            elif len(good_matches) == 0:
                print("There are no matches.")
                # If there is no matches need to do something.
                # Perhaps the comic is new and hasnt
                # been uploaded onto comicvine.
            elif len(good_matches) > 1:
                for i in good_matches:
                    print(i["volume"]["name"])
                self.results.extend(good_matches)
                # Need to use scoring or sorting or closest title match etc.
                # If that cant decide then we need to flag the comic
                # and ask the user for input.
        if len(self.results) == 0:
            print("There are no matches")
            return MatchCode.NO_MATCH, potential_results
            filterer = ResultsFilter(potential_results, self.data, self.path)
            self.filtered_for_none = filterer.present_choices()
            return MatchCode.NO_MATCH
        elif len(self.results) > 1:
            print("There are multiple matches")
            return MatchCode.MULTIPLE_MATCHES, self.results
            filterer = ResultsFilter(self.results, self.data, self.path)
            self.filtered_for_many = filterer.present_choices()
            return MatchCode.MULTIPLE_MATCHES


class TagApplication:
    def __init__(self, comicvine_dict: dict | list, api_key: str, filename: str):
        if isinstance(comicvine_dict, list):
            entry = comicvine_dict[0]
        else:
            entry = comicvine_dict
        self.link = entry["api_detail_url"]
        self.issue_id = entry["id"]
        self.volume_id = entry["volume"]["id"]
        self.pub_link = entry["volume"]["api_detail_url"]
        self.api_key = api_key
        self.filename = filename
        self.url: Optional[str] = None
        self.issue_data = None
        self.final_info: Optional[dict] = None

    def build_url(self) -> None:
        req = requests.Request(
            method="GET",
            url=self.link,
            params={
                "api_key": self.api_key,
                "format": "json",
            },
        )
        prepared = req.prepare()
        self.url = prepared.url

    def get_publisher(self) -> None:
        url = f"{self.pub_link}?api_key={self.api_key}&format=json"
        response = session.get(url)
        data = response.json()
        return data["results"]["publisher"]["name"]

    def get_request(self) -> None:
        if not self.url:
            self.build_url()
        if self.url is None:
            raise ValueError("url cannot be None")
        response = session.get(self.url)
        if response.status_code != 200:
            print(f"Request failed with status code: {response.status_code}")
        data = response.json()
        print(data["results"])
        self.issue_data = data["results"]

    def parse_list_of_dicts(self, field) -> list[str]:
        if self.issue_data is None:
            raise ValueError("issue_data cannot be None")
        entries = self.issue_data[field]
        things = []
        for entry in entries:
            things.append(entry["name"])
        return things

    def create_metadata_dict(self) -> dict:
        if self.issue_data is None:
            raise ValueError("issue_data cannot be None")
        date_str = self.issue_data["cover_date"]
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        year = date_obj.year
        month = date_obj.month
        simple_info = ComicInfo(
            primary_key="temp",
            filepath="temp",
            original_filename=self.filename,
            title=self.issue_data["name"],
            series=self.issue_data["volume"]["name"],
            volume_num=self.issue_data["issue_number"],
        )
        processor = MetadataProcessing(simple_info)
        clean_title_info = processor.title_parsing()

        information: dict = {
            "Title": clean_title_info["title"],
            "Series": clean_title_info["series"],
            "Number": clean_title_info["volume_num"],
            "Publisher": self.get_publisher(),
            "Month": month,
            "Year": year,
            "Summary": self.issue_data["description"],
            "Characters": ", ".join(
                self.character_or_team_parsing(self.issue_data["character_credits"])
            ),
            "Teams": ", ".join(
                self.character_or_team_parsing(self.issue_data["team_credits"])
            ),
            "api_link": self.issue_data["api_detail_url"],
        }

        information.update(
            self.creators_entry_parsing(self.issue_data["person_credits"])
        )
        self.final_info = information
        return information

    @staticmethod
    def creators_entry_parsing(list_of_creator_info: list[dict]) -> dict[str, str]:
        mapping = {
            "penciler": "Penciller",
            "writer": "Writer",
            "inker": "Inker",
            "editor": "Editor",
            "letterer": "Letterer",
            "cover": "CoverArtist",
            "colorist": "Colorist",
            "artist": "Penciller",
        }
        creator_dict = {v: "" for v in mapping.values()}

        for info in list_of_creator_info:
            roles = [r.strip().lower() for r in info["role"].split(",")]
            for role in roles:
                if role in mapping:
                    key = mapping[role]
                    if creator_dict[key]:
                        creator_dict[key] += ", " + info["name"]
                    else:
                        creator_dict[key] = info["name"]

        return creator_dict

    @staticmethod
    def character_or_team_parsing(list_of_info: list[dict]) -> list[str]:
        peoples = []
        for i in list_of_info:
            peoples.append(str(i["name"]))
        return peoples

    def fill_gaps(self):
        MANDATORY_FIELDS = {
            "Writer",
            "Penciller",
            "Year",
            "Summary",
            "Number",
            "Series",
            "Title",
        }

        for field in MANDATORY_FIELDS:
            if field not in self.final_info or not self.final_info[field]:
                self.final_info[field] = "PENDING"
        for key in self.final_info:
            if key not in MANDATORY_FIELDS:
                if self.final_info[key] is None or self.final_info[key] == "":
                    self.final_info[key] = "MISSING"

    def create_xml(self) -> bytes:
        root = ET.Element("ComicInfo")

        if self.final_info is None:
            raise ValueError("final_info cannot be None")
        for key, value in self.final_info.items():
            child = ET.SubElement(root, key)
            child.text = str(value)

        xml_bytes_io = BytesIO()
        tree = ET.ElementTree(root)
        tree.write(xml_bytes_io, encoding="utf-8", xml_declaration=True)
        return xml_bytes_io.getvalue()

    def insert_xml_into_cbz(self, cbz_path: str):
        if not os.path.exists(cbz_path):
            raise FileNotFoundError(f"{cbz_path} does not exist")
        self.fill_gaps()
        xml_content = self.create_xml()

        with zipfile.ZipFile(cbz_path, "a") as cbz:
            cbz.writestr("ComicInfo.xml", xml_content)


def run_tagging_process(filepath, api_key) -> Optional[tuple[list, RequestData]]:
    filename = Path(filepath).stem
    lexer_instance = Lexer(filename)
    state: Optional[LexerFunc] = run_lexer
    while state is not None:
        state = state(lexer_instance)
    parser_instance = Parser(lexer_instance.items)
    comic_info = parser_instance.construct_metadata()
    print(comic_info)
    series = comic_info["series"]
    num = comic_info.get("issue", 0) or comic_info.get("volume", 0)
    year = comic_info.get("year", 0)
    title = comic_info.get("title")

    data = RequestData(int(num), int(year), str(series), str(title))

    tagger = TaggingPipeline(data=data, path=filepath, size=100, api_key=api_key)

    final_result = tagger.run()
    if final_result == MatchCode.ONE_MATCH:

        inserter = TagApplication(tagger.results[0], api_key, filename)
        inserter.get_request()
        inserter.create_metadata_dict()
        inserter.insert_xml_into_cbz(filepath)
        return None
    elif final_result[0] == MatchCode.NO_MATCH:
        return (final_result[1], tagger.data)
        print("Need another method to find matches")
        best_matches = tagger.filtered_for_none
        return (best_matches, tagger.data)
        # Add a method to rank and return the best 3-5 matches.
    elif final_result[0] == MatchCode.MULTIPLE_MATCHES:
        return (final_result[1], tagger.data)
        print("Multiple matches, require user input to disambiguate.")
        best_matches = tagger.filtered_for_many
        return (best_matches, tagger.data)
        # Need to create a gui popup to allow user to select correct match.
    else:
        raise ValueError("Something has gone wrong")


def extract_and_insert(match, api_key, filename, filepath):
    inserter = TagApplication(match, api_key, filename)
    inserter.get_request()
    inserter.create_metadata_dict()
    inserter.insert_xml_into_cbz(filepath)
    return None

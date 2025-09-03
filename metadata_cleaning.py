import calendar
import re
import traceback

from fuzzywuzzy import fuzz
from word2number import w2n

from classes.helper_classes import ComicInfo
from database.db_utils import get_publisher_info
from file_utils import normalise_publisher_name

SERIES_OVERRIDES = [
    ("tpb", 1, "TPB"),
    ("omnibus", 2, "Omni"),
    ("modern era epic collection", 4, "MEC"),
    ("epic collection", 3, "EC"),
]


class PublisherNotKnown(KeyError):
    def __init__(self, publisher_name):
        self.publisher_name = publisher_name
        super().__init__(f"Publisher: '{publisher_name}' not known.")


class MetadataProcessing:
    def __init__(self, raw_dict: ComicInfo) -> None:
        self.raw_info = raw_dict
        self.filepath = raw_dict.filepath
        self.title_info: dict[str, str | int] = {}

    def __enter__(self):
        print(f"[INFO] Starting metadata processing for {self.filepath}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            print(f"[ERROR] Exception while processing {self.filepath}: {exc_val}")
            traceback.print_tb(exc_tb)
        else:
            print(f"[INFO] Sucessfully finished processing {self.filepath}")
        return False

    PATTERNS: list[re.Pattern] = [
        re.compile(r"\bv(?P<num>)\d{1,3}\b", re.I),
        re.compile(r"\b(?P<num>\d{3})\b"),
        re.compile(r"\bvol(?:ume)?\.?\s*(?P<num>\d{1,3})\b", re.I),
    ]

    SPECIAL_PATTERN = re.compile(r"\bv(?P<volume>\d{1,3})\s+(?P<issue>\d{2,3})\b", re.I)

    @staticmethod
    def title_case(title: str) -> str:
        # Need to also make this capitalise things like X-Men not X-men.
        minor_words = {
            "a",
            "an",
            "and",
            "as",
            "at",
            "but",
            "by",
            "for",
            "in",
            "nor",
            "of",
            "on",
            "or",
            "so",
            "the",
            "to",
            "up",
            "yet",
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

    def match_publisher(self) -> tuple[int, str]:
        """
        Matches the natural language name of a publisher from metadata
        to an entry in the list of known publishers with numbered keys from
        the sql table.
        This uses fuzzy matches due to alterations of publisher names.

        Args:
            raw_pub_name: The string extracted from ComicInfo.xml to be matched.

        Returns:
            The ID of the best-matching known publisher.

        Raises:
            KeyError: If no known publisher matches closely enough.
        """
        known_publishers = get_publisher_info()
        best_score = 0
        best_match = None
        raw_pub_name = self.raw_info.publisher if self.raw_info.publisher else "Marvel"
        normalised_pub_name = normalise_publisher_name(raw_pub_name)
        for pub_id, pub_name, clean_name in known_publishers:
            score = fuzz.token_set_ratio(normalised_pub_name, clean_name)
            if score > best_score:
                best_match = (pub_id, pub_name)
                best_score = score
        if best_score >= 80 and best_match:
            return best_match
        else:
            # TODO: Add the raw_pub_name to the database.
            raise PublisherNotKnown(raw_pub_name)

    def title_parsing(self) -> dict[str, str | int]:
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

        out: dict[str, str | int] = {}
        common_title_words = {"tpb", "hc"}
        if self.raw_info.title and self.raw_info.series:
            title_raw = self.raw_info.title.lower()
            series_raw = self.raw_info.series.lower()

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
        for keyword, type_id, _ in SERIES_OVERRIDES:
            if keyword in series_name.lower():
                collection_type = type_id
                break
            if keyword in collection_title.lower():
                collection_type = type_id
                break

        volume_match = re.match(
            r"(?:vol(?:ume)?|book)\.?\s*(\d+|one|two|three|four|five|six|"
            + r"seven|eight|nine|ten|eleven|twelve)\s*[:\-]?\s*(.*)",
            title_raw,
            re.I,
        )

        issue_number = None
        rest_title = None

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

        if issue_number is None:
            self.title_info["title"] = str(self.raw_info.title)
            self.title_info["series"] = str(self.raw_info.series)
            self.title_info["collection_type"] = collection_type
            self.title_info["volume_num"] = (
                0 if self.raw_info.volume_num is None else self.raw_info.volume_num
            )
            return self.title_info

        else:
            out["title"] = self.title_case(collection_title)
            out["series"] = self.title_case(series_name)
            out["collection_type"] = collection_type
            out["volume_num"] = issue_number
            self.title_info = out
            return out

    def check_issue_numbers_match(self) -> bool:
        if self.title_info is None:
            self.title_parsing()
        if "volume_num" not in self.title_info:
            return False
        return self.raw_info.volume_num == self.title_info["volume_num"]

    def extract_volume_num_from_filepath(self) -> tuple[int, int]:
        fname = (
            self.raw_info.original_filename
            if self.raw_info.original_filename is not None
            else ""
        )

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
        volume, _ = self.extract_volume_num_from_filepath()
        if volume > 0:
            return volume
        if self.raw_info.volume_num:
            try:
                return int(self.raw_info.volume_num)
            except (ValueError, TypeError):
                pass
        return 0
        #  Need extra logic here to get the correct volume/issue number

    def create_date_string(self) -> str:
        return f"{self.raw_info.month}/{self.raw_info.year}"

    def run(self) -> ComicInfo:
        self.title_parsing()

        volume = self.volume_number_parsing()

        date_str = self.create_date_string()

        publisher_id, publisher_name = self.match_publisher()

        self.out_data = self.raw_info.model_copy(
            update={
                "title": self.title_info["title"],
                "series": self.title_info["series"],
                "publisher": publisher_name,
                "collection_type": self.title_info["collection_type"],
                "volume_num": volume,
                "date": date_str,
                "publisher_id": publisher_id,
            }
        )
        return self.out_data

    @staticmethod
    def sanitise(filename: str) -> str:
        santised = re.sub(r'[<>:"/\\|?*]', "-", filename)
        santised = santised.rstrip(" .")
        return santised

    def new_filename_and_folder(self) -> tuple[str, int]:
        date_suffix = f"{calendar.month_abbr[self.out_data.month]} {self.out_data.year}"
        volume_num = self.out_data.volume_num
        collection_id = self.out_data.collection_type
        for _, val, abbr in SERIES_OVERRIDES:
            if val == collection_id:
                collection_name = abbr.strip()
                break
        series_name = self.sanitise(self.out_data.series).strip()
        title_name = self.sanitise(self.out_data.title).strip()
        filename = f"{series_name} - {title_name} {collection_name} #0{volume_num} ({date_suffix}).cbz"  # noqa: E501
        filename = self.sanitise(filename).strip()
        return filename, self.out_data.publisher_id

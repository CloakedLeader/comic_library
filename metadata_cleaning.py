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
        print(f"[INFO] Starting metadata processing for {self.filepath.name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            print(f"[ERROR] Exception while processing {self.filepath.name}: {exc_val}")
            traceback.print_tb(exc_tb)
        else:
            print(f"[INFO] Sucessfully finished processing {self.filepath.name}")
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

        # ! Function rewritten so may have broken.

        title_raw = (self.raw_info.title or "").lower()
        series_raw = (self.raw_info.series or "").lower()

        def split_title_and_series(raw_title: str, raw_series: str) -> tuple[str, str]:
            """
            Deterine series name and collection based on ':' placement.

            Args:
                raw_title (str): The title as captured from API.
                raw_series (str): The series name as captured from API.

            Returns:
                tuple[str, str]: (series_name, collection_title)
            """

            if ":" in raw_title:
                preterm, collection_title = map(str.strip, raw_title.split(":", 1))

                if has_volume_signifier(preterm):
                    return raw_series.strip(), collection_title
                else:
                    return preterm.strip(), collection_title

            # else:
            #     if has_volume_signifier(raw_title):
            #         return raw_series.strip(), ""

            if ":" in raw_series:
                series, title = map(str.strip, raw_series.split(":", 1))
                return series, title

            return raw_series.strip(), raw_title.strip()

        def has_volume_signifier(term: str) -> bool:
            volume_pattern = re.compile(r"\b(vol(?:ume)?|book)\b", re.I)
            return bool(volume_pattern.search(term))

        def normalise_collection_title(collection_title: str, series_name: str) -> str:
            """Replace ambiguous titles like 'tpb' or 'hc"""

            if collection_title in {"tpb", "hc"}:
                return series_name
            return collection_title

        def get_collection_type(collection_title: str, series_name: str) -> int:
            """Determine collection type via SERIES_OVERRRIDES."""

            for keyword, type_id, _ in SERIES_OVERRIDES:
                if (
                    keyword in series_name.lower()
                    or keyword in collection_title.lower()
                ):
                    return type_id
            return 1

        def parse_volume_number(raw_title: str) -> tuple[int | None, str | None]:
            """
            Parses volume numbers like 'Vol. 2', 'Book One', etc.


            Args:
                raw_title (str): The title to be cleaned of unhelpful terms.

            Returns:
                tuple[int | None, str | None]: (volume_number or None, remaining_title or None)
            """

            pattern = (
                r"(?:vol(?:ume)?|book)\.?\s*"
                r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
                r"eleven|twelve)\s*[:\-]?\s*(.*)"
            )

            match = re.match(pattern, raw_title, re.I)
            if not match:
                return None, None

            num_text = match.group(1).lower()
            rest = match.group(2).strip().lower()

            if num_text.isdigit():
                volume_num = int(num_text)
            else:
                try:
                    volume_num = int(w2n.word_to_num(num_text))
                except ValueError:
                    volume_num = 0  #! Need a logic check later as 0 signals error!.
            return volume_num, rest

        series_name, collection_title = split_title_and_series(title_raw, series_raw)
        collection_title = normalise_collection_title(collection_title, series_name)
        collection_type = get_collection_type(series_name, collection_title)

        volume_num, rest_title = parse_volume_number(title_raw)

        if rest_title:
            if collection_title != rest_title:
                # TODO: Some logic here.
                # collection_title = rest_title
                pass

        if volume_num is None:
            print("Could not find a good volume number!")
            # self.title_info["title"] = str(self.raw_info.title)
            # self.title_info["series"] = str(self.raw_info.series)
            self.title_info["title"] = self.title_case(collection_title)
            self.title_info["series"] = self.title_case(series_name)
            self.title_info["collection_type"] = collection_type
            self.title_info["volume_num"] = self.raw_info.volume_num or 0
            return self.title_info

        self.title_info["title"] = self.title_case(collection_title)
        self.title_info["series"] = self.title_case(series_name)
        self.title_info["collection_type"] = collection_type
        self.title_info["volume_num"] = volume_num
        return self.title_info

    def check_issue_numbers_match(self) -> bool:
        if self.title_info is None:
            self.title_parsing()
        if "volume_num" not in self.title_info:
            return False
        return self.raw_info.volume_num == self.title_info["volume_num"]

    def extract_volume_num_from_filename(self) -> tuple[int, int]:
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
        volume, _ = self.extract_volume_num_from_filename()
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
        if not hasattr(self, "out_data"):
            self.run()

        date_suffix = f"{calendar.month_abbr[self.out_data.month]} {self.out_data.year}"  # type: ignore
        volume_num = self.out_data.volume_num
        collection_id = self.out_data.collection_type
        collection_name = ""
        for _, val, abbr in SERIES_OVERRIDES:
            if val == collection_id:
                collection_name = abbr.strip()
                break
        series_name = self.sanitise(str(self.out_data.series)).strip()
        title_name = self.sanitise(str(self.out_data.title)).strip()
        filename = f"{series_name} - {title_name} {collection_name} #0{volume_num} ({date_suffix}).cbz"  # noqa: E501
        filename = self.sanitise(filename).strip()
        return filename, self.out_data.publisher_id  # type: ignore

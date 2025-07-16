import re
from fuzzywuzzy import fuzz
from word2number import w2n
import os
from helper_classes import ComicInfo


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

    SPECIAL_PATTERN = re.compile(r"\bv(?P<volume>\d{1,3})\s+(?P<issue>\d{2,3})\b)",
                                 re.I)

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
            r"(?:vol(?:ume)?|book)\.?\s*(\d+|one|two|three|four|five|six|" /
            r"seven|eight|nine|ten|eleven|twelve)\s*[:\-]?\s*(.*)",
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

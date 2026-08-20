import logging
import re
from difflib import SequenceMatcher
from typing import Callable, TypeAlias

from rapidfuzz import fuzz

from my_project.classes.helper_classes import (
    ComicVineIssueStruct,
    ComicVineSearchStruct,
)
from my_project.classes.tagging_classes import Candidate, Queries

from .requester import RequestData

logger = logging.getLogger(__name__)

ComicVineResponseList: TypeAlias = (
    list[ComicVineIssueStruct] | list[ComicVineSearchStruct]
)
ComicVineResponse: TypeAlias = ComicVineIssueStruct | ComicVineSearchStruct


class SearchResponseValidator:
    def __init__(
        self, response: list[ComicVineSearchStruct], expected_data: RequestData
    ):
        self.results = response
        self.expected_info = expected_data
        self.mutable_results = response

    def filter_results(self, predicate: Callable) -> list[ComicVineSearchStruct]:
        """
        Filter stored results using some predicate.

        Args:
            predicate (Callable): A function that recieves a single result
                item and returns a truthy value to include that item.

        Returns:
            list: The subset of 'self.results' which fulfills the predicate.
        """
        self.mutable_results = [
            item for item in self.mutable_results if predicate(item)
        ]
        return self.mutable_results

    def issue_count_filter(self, limit: int = 12) -> list[ComicVineSearchStruct]:
        """
        Filter results to exclude items that have too many issues.

        Args:
            limit (int, optional): Maximum number of issues to be considered a series
                of collected editions. Defaults to 12.

        Returns:
            list: A list of result items from self.results whose count is less than 12.
        """

        def is_collection(item: ComicVineSearchStruct) -> bool:
            issue_count = item.count_of_issues
            if issue_count is None:
                return True
            else:
                return True if issue_count < limit else False

        return self.filter_results(is_collection)

    def pick_best_volumes(self, number: int = 7) -> list[ComicVineSearchStruct]:
        """
        Selects the top matching volume results whose names best match the expected
        series name.

        Args:
            number (int, optional): Maximum number of top-matching results to return.
                Defaults to 5.

        Returns:
            list: The selected result dictionaries ordered from highest to lowest via
                the name-match score.
        """

        def score_name(item: ComicVineSearchStruct) -> float:
            score = 0.0
            name = item.name
            if name:
                score += SequenceMatcher(
                    None, name.lower(), self.expected_info.series.lower()
                ).ratio()
            return score

        scored_volumes = [
            (i, score_name(item)) for i, item in enumerate(self.mutable_results)
        ]
        scored_volumes.sort(key=lambda x: x[1], reverse=True)
        top_indices = [i for i, _ in scored_volumes[:number]]
        self.mutable_results = [self.mutable_results[i] for i in top_indices]
        return self.mutable_results

    def pub_checker(self) -> list[ComicVineSearchStruct]:
        """
        Filter a list of results by publisher credibility.

        Filters out results which are published by foreign publishers.
        Specifically looks for common english-language publisher keywords.

        Args:
            results (list): A list of results that include a "publisher" dictionary.

        Returns:
            list: The filtered list of result dictionaries that passed the publisher
                checks.
        """

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

        filtered: list[ComicVineSearchStruct] = []
        for result in self.mutable_results:
            if result.publisher is None:
                continue
            pub_id = result.publisher.id
            pub_name = result.publisher.name
            if pub_id in english_publishers.values():
                filtered.append(result)
            elif any(word.lower() in foriegn_keywords for word in pub_name.split()):
                logger.info(f"Filtered out {pub_name} due to foreign publisher.")
            else:
                filtered.append(result)
                logger.info(f"Accepted '{pub_name}' but please check.")
        self.mutable_results = filtered
        return filtered

    def filter_search_results(self) -> list[ComicVineSearchStruct]:
        """
        Combines many filters and checks to reduce the number of results to a more reasonable amount
        to check.

        Returns:
            list[ComicVineSearchStruct]: The remaining results once all the filering has been completed.
        """
        self.pub_checker()
        self.issue_count_filter()
        self.pick_best_volumes()
        return self.mutable_results


class IssueResponseValidator:
    ISSUE_THRESHOLD = 70
    VOLUME_THRESHOLD = 50

    def __init__(self, expected_data: RequestData) -> None:
        """
        Initialise the validator with API response results and the expected
        request data.

        Args:
            response (dict): API response containing a "results" key whose
                value is a list of result dictionaries.
            expected_data (RequestData): Expected metadata for the request
                to return.
        """

        self.expected_info = expected_data

    @staticmethod
    def get_year(data: ComicVineIssueStruct) -> int:
        return int(data.date_added[:4])

    @staticmethod
    def fuzzy_match(a: str, b: str, threshold: int = 65) -> bool:
        """
        Determine similarity of two strings using token-sort fuzzy matching.

        Args:
            a (str): First string to compare.
            b (str): Second string to compare.
            threshold (int, optional): Minimum similarity percentage to consider
                strings a match. Defaults to 65.

        Returns:
            bool: True if the strings similarity is greater or equal to 'threshold'.
                False otherwise.
        """

        return fuzz.token_sort_ratio(a, b) >= threshold

    @staticmethod
    def is_ambig_name(name: str | None) -> bool:
        ambig_names = ["tpb", "hc", "omnibus"]
        ambig_regexes = [
            r"^vol(?:ume)?\.?\s*\d+$",  # matches "vol.", "volume", "vol"
            r"^#\d+$",  # matches "#1", "#1 2" etc
            r"^issue\s*\d+$",  # matches "issue 3"
            r"\bvol(?:ume)?\.?\s*(one|two|three|four|\d+|i{1,3}|iv|v)\b",
            r"\bbook\s*(one|two|three|four|\d+|i{1,3}|iv|v)\b",
        ]
        if name:
            lowered_name = name.lower().strip()
            if lowered_name in ambig_names or any(
                re.match(p, lowered_name) for p in ambig_regexes
            ):
                return True
            else:
                return False
        return False

    @staticmethod
    def get_proper_title(name: str | None, volume_name: str | None) -> str:
        ambig_names = ["tpb", "hc", "omnibus"]
        ambig_regexes = [
            r"^vol(?:ume)?\.?\s*\d+$",  # matches "vol.", "volume", "vol"
            r"^#\d+$",  # matches "#1", "#1 2" etc
            r"^issue\s*\d+$",  # matches "issue 3"
            r"\bvol(?:ume)?\.?\s*(one|two|three|four|\d+|i{1,3}|iv|v)\b",
            r"\bbook\s*(one|two|three|four|\d+|i{1,3}|iv|v)\b",
        ]
        if name:
            lowered_name = name.lower().strip()
            if lowered_name in ambig_names or any(
                re.match(p, lowered_name) for p in ambig_regexes
            ):
                if not volume_name:
                    raise ValueError("No name for issue found.")
                else:
                    return volume_name
            else:
                return name

        else:
            if not volume_name:
                raise ValueError("No name for issue found.")
            else:
                return volume_name

    def score_title(self, title: str) -> float:
        sim = SequenceMatcher(
            None, title.casefold(), self.expected_info.title.casefold()
        ).ratio()
        return sim**2.5

    def score_series(self, series: str, queries: Queries) -> float:
        if (
            series.casefold()
            == f"{queries.series.casefold()}: {queries.title.casefold()}"
        ):
            return 1.0
        sim = SequenceMatcher(
            None, series.casefold(), self.expected_info.series.casefold()
        ).ratio()
        return sim**2.5

    def score_year(self, year: int) -> float:
        difference = abs(self.expected_info.pub_year - year)

        if difference == 0:
            return 1.0
        elif difference == 1:
            return 0.50
        elif difference == 2:
            return 0.2
        elif difference == 3:
            return 0.05
        else:
            return 0.0

    def score_result(
        self, issue_data: ComicVineIssueStruct, queries: Queries
    ) -> Candidate:
        title = self.get_proper_title(issue_data.name, issue_data.volume.name)
        if issue_data.name is None or self.is_ambig_name(issue_data.name):
            title_score = None
        else:
            title_score = self.score_title(issue_data.name)

        series_score = self.score_series(issue_data.volume.name, queries)
        year = self.get_year(issue_data)
        year_score = self.score_year(year)

        # TODO: Implement publisher scoring based on ComicVineSearch results.
        # ! Need to pass around the imposed title so that fuzzy matching methods all compare to the same thing.
        return Candidate(
            name=title,
            issue=issue_data,
            title_score=title_score,
            series_score=series_score,
            year_score=year_score,
        )

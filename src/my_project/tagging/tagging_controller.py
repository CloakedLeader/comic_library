import logging
import math
import zipfile
from enum import IntEnum
from io import BytesIO
from pathlib import Path

import requests

from my_project.classes.helper_classes import (
    ComicVineIssueStruct,
    ComicVineSearchStruct,
    IdSet,
    Publisher,
)
from my_project.classes.tagging_classes import Candidate, Queries
from my_project.tagging.image_scoring import ImageScorer
from my_project.tagging.lexer import Lexer
from my_project.tagging.parser import Parser
from my_project.tagging.requester import HttpRequest, RequestData
from my_project.tagging.validator import IssueResponseValidator, SearchResponseValidator

logger = logging.getLogger(__name__)

HASH_SIZE = 16


class MatchCode(IntEnum):
    NO_MATCH = 0
    ONE_MATCH = 1
    MULTIPLE_MATCHES = 2


class NoSearchResultsError(Exception):
    """Raised after filtering the search results and none remain."""


class VolumeNotFoundError(Exception):
    """Raised when a requested volume cannot be found in the search results."""


header = {
    "User-Agent": "AutoComicLibrary/1.0 (contact: adam.perrott@protonmail.com;"
    "github.com/CloakedLeader/comic_library)",
    "Accept": r"*/*",
    "Referer": "https://comicvine.gamespot.com/",
    # "Accept-Encoding": "gzip,deflate,br",
    "Connection": "keep-alive",
}
session = requests.Session()
session.headers.update(header)


class TaggingPipeline:
    def __init__(
        self, data: RequestData, path: Path, size: float, api_key: str
    ) -> None:
        self.data = data
        self.path = path
        self.size = size
        self.http = HttpRequest(data, api_key, session)
        self.cover = self.cover_getter()
        self.result: ComicVineIssueStruct | None = None
        self.issue_validator = IssueResponseValidator(expected_data=data)
        self.candidates: list[Candidate] = []
        self.image_scorer = ImageScorer(self.cover, self.http)
        self.queries = Queries(
            combined=f"{self.data.series} {self.data.title or ''}".strip(),
            series=self.data.series,
            title=self.data.title,
        )

    def cover_getter(self):
        with zipfile.ZipFile(str(self.path), "r") as zip_ref:
            image_files = [
                f
                for f in zip_ref.namelist()
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if not image_files:
                logger.info(f"Empty archive in {self.path}")
                raise ValueError("Empty archive.")

            image_files.sort()
            cover = zip_ref.read(image_files[0])
            return BytesIO(cover)

    def get_search_results(self) -> IdSet[ComicVineSearchStruct]:
        search_results = IdSet[ComicVineSearchStruct]()
        for q in self.queries:
            if q == "":
                continue
            self.http.build_url_search(q)
            results = self.http.search_get_request()
            search_results.extend(results.results)

        return search_results

    def score_issue_metadata(self, data: ComicVineIssueStruct) -> Candidate:
        return self.issue_validator.score_result(data, self.queries)

    @staticmethod
    def deduplicate_candidates(candidates: list[Candidate]) -> list[Candidate]:
        present_ids: set[int] = set()
        unique_candidates: list[Candidate] = []
        for entry in candidates:
            if entry.issue.id in present_ids:
                continue
            else:
                unique_candidates.append(entry)
                present_ids.add(entry.issue.id)

        return unique_candidates

    def run(self) -> MatchCode:
        total_candidates = []
        self.search_results = self.get_search_results()
        self.search_validator = SearchResponseValidator(
            list(self.search_results), self.data
        )

        logger.info(f"There are {len(self.search_results)} results returned.")
        filtered_results = self.search_validator.filter_search_results()
        if len(filtered_results) == 0:
            raise NoSearchResultsError()

        logger.info(
            "After filtering search results for title, publisher and issue "
            + f"there are {len(filtered_results)} remaining results."
        )

        vol_info = [(i.id, i.name) for i in filtered_results]
        for j, k in vol_info:
            self.http.build_url_iss(j)
            issue_results = self.http.issue_get_request()
            logger.info(
                f"There are {len(issue_results.results)}"
                + f" issues in the matching volume: '{k}'."
            )

            candidates = [
                self.score_issue_metadata(data) for data in issue_results.results
            ]

            if len(candidates) == 0:
                logger.info("No issues from this volume meet the threshold.")
                continue

            total_candidates.extend(candidates)

        total_candidates = self.deduplicate_candidates(total_candidates)
        logger.info(f"Length of possible matches: {len(total_candidates)}")
        total_candidates.sort(
            key=lambda candidate: candidate.metadata_score,
            reverse=True,
        )
        if total_candidates:
            n = len(total_candidates)
            cutoff = max(6, int(6 + 2 * math.log2(n / 6)))
            self.candidates = total_candidates[: min(n, cutoff)]
        else:
            self.candidates = []
        # I now have a list self.candidates which contains all possible results.
        self.candidates = self.image_scorer.score_candidate_images(self.candidates)
        for i in self.candidates:
            logger.info(i.__repr__())

        if len(self.candidates) == 1:
            candidate = self.candidates[0]
            if candidate.confidence_score > 0.9:
                logger.info(
                    f"Strong match: {candidate.issue.volume.name} "
                    f"(score={candidate.confidence_score:.3f})"
                )
                logger.info(f"The match is: {candidate.issue.volume.name}")
                self.result = candidate.issue
                return MatchCode.ONE_MATCH
            else:
                return MatchCode.NO_MATCH

        elif len(self.candidates) == 0:
            return MatchCode.NO_MATCH
            # look at previous results before filtering and try to rank them for presentation to user.

        else:
            ranked_candidates = sorted(
                self.candidates,
                key=lambda candidate: candidate.confidence_score,
                reverse=True,
            )
            best = ranked_candidates[0]
            second_best = ranked_candidates[1]
            score_difference = best.confidence_score - second_best.confidence_score
            logger.info(
                f"Best candidate: {best.issue.volume.name} "
                f"(score={best.confidence_score:.3f})"
            )
            logger.info(
                f"Second candidate: {second_best.issue.volume.name} "
                f"(score={second_best.confidence_score:.3f})"
            )
            logger.info(f"Score difference: {score_difference:.3f}")
            if score_difference >= 0.25 and best.confidence_score >= 0.7:
                logger.info(f"Strong relative match: {best.issue.volume.name}")
                self.result = best.issue
                return MatchCode.ONE_MATCH
            return MatchCode.MULTIPLE_MATCHES
            # ? Rank candidates and see if one sticks out as the best by far.

    def get_publisher_info(self, volume_id: int) -> Publisher:
        for i in self.search_results:
            if i.id == volume_id:
                return i.publisher

        raise VolumeNotFoundError(f"No publisher found for volume {volume_id}.")


def run_tagging_process(
    filepath: Path, api_key: str
) -> tuple[TaggingPipeline, MatchCode]:
    filename = filepath.stem

    lexer_instance = Lexer(filename)
    logger.info("Starting lexing the filename.")
    lexer_instance.run()
    logger.info(lexer_instance.format_items())

    parser_instance = Parser(lexer_instance.items)
    logger.info("Starting parsing lexed items.")
    comic_info = parser_instance.parse()
    logger.info(f"The filename {filename} gives the following info:\n {comic_info}")

    series = comic_info.series
    num = comic_info.volume_number
    year = comic_info.year
    title = comic_info.title

    data = RequestData(num, year, series, title)
    logger.info(f"The expected complete title is: {data.unclean_title}")

    tagger = TaggingPipeline(
        data=data, path=filepath, size=filepath.stat().st_size, api_key=api_key
    )

    return (tagger, tagger.run())

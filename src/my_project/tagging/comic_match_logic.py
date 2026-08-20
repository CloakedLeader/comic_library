import logging
from difflib import SequenceMatcher
from pathlib import Path
from typing import TypedDict, cast

from my_project.classes.helper_classes import ComicVineIssueStruct
from my_project.classes.tagging_classes import Candidate
from my_project.tagging.requester import RequestData

logger = logging.getLogger(__name__)


class ComicMatch(TypedDict):
    title: str
    series: str
    year: int
    number: int
    cover_link: str
    description: str
    id: int


class ResultsFilter:
    def __init__(
        self,
        query_results: list[Candidate],
        expected_info: RequestData,
        filepath: Path,
    ):
        self.query_results = query_results
        self.expected_info = expected_info
        self.filepath = filepath

    def __enter__(self):
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Entering ResultsFilter context for: {self.filepath.name}")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            logger.error(f"Exception occured: {exc_type.__name__}: {exc_value}")
        else:
            logger.info("Exiting ResultsFilter context cleanly.")
        return False

    def title_similarity(self, candidate_title: str) -> float:
        return SequenceMatcher(
            None, candidate_title.lower(), self.expected_info.title.lower()
        ).ratio()

    def volume_similarity(self, candidate_series: str) -> float:
        return SequenceMatcher(
            None, candidate_series.lower(), self.expected_info.series.lower()
        ).ratio()

    def year_match(self, candidate_year: int) -> float:
        if not self.expected_info.pub_year:
            return 0.5
        return 1.0 if candidate_year == self.expected_info.pub_year else 0.0

    def number_match(self, candidate_number: int) -> float:
        if not self.expected_info.num:
            return 0.5
        return 1.0 if candidate_number == self.expected_info.num else 0.0

    def score_results(self, result: Candidate) -> float:
        issue_num = cast(str, result.issue.issue_number)

        score = 0.0
        score += result.title_score if result.title_score else 0.0
        score += result.series_score
        score += result.year_score
        score += result.image_score if result.image_score else 0.0
        score += self.number_match(int(issue_num))

        return score

    def filter_results(self, top_n: int = 5) -> list[tuple[ComicVineIssueStruct, int]]:
        logger.debug("Filtering %d query results.", len(self.query_results))
        ids: set[int] = set()
        scored: list[tuple[float, ComicVineIssueStruct, int]] = []
        # Each tuple has (score, result, position)
        for index, result in enumerate(self.query_results):
            indiv_id = int(result.issue.id)
            if indiv_id not in ids:
                ids.add(indiv_id)
            else:
                continue
            scored.append((self.score_results(result), result.issue, index))

        scored.sort(key=lambda x: x[0], reverse=True)
        for i in scored:
            logger.info(f"Name: {i[1].name}    Position: {i[2]}     Score: {i[0]}")
        return [(r, position) for _, r, position in scored[:top_n]]

    def present_choices(self) -> list[tuple[ComicMatch, int]]:
        top_results = self.filter_results()
        best_results: list[tuple[ComicMatch, int]] = []
        for r, position in top_results:
            typedict: ComicMatch = {
                "title": str(r.name),
                "series": str(r.volume.name),
                "year": int(str(r.cover_date)[:4]),
                "number": int(r.issue_number),
                "cover_link": str(r.image.thumb_url),
                "description": str(r.description),
                "id": int(r.id),
            }
            best_results.append((typedict, position))

        return best_results

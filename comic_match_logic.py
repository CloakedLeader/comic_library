from difflib import SequenceMatcher
from pathlib import Path
from typing import TypedDict, cast

from tagging_controller import RequestData


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
        self, query_results: list[dict], expected_info: RequestData, filepath: str
    ):

        self.query_results = query_results
        self.expected_info = expected_info
        self.filepath = Path(filepath)

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

    def score_results(self, result: dict) -> float:
        name = cast(str, result.get("name"))
        volume = cast(dict, result.get("volume"))
        cover_date = cast(str, result.get("cover_date"))
        issue_num = cast(str, result.get("issue_number"))

        score = 0.0
        score += self.title_similarity(name)
        score += self.volume_similarity(volume.get("name") or "")
        score += self.year_match(int(cover_date[4:]))
        score += self.number_match(int(issue_num))
        return score

    def filter_results(self, top_n: int = 5) -> list[dict]:
        scored = [(self.score_results(r), r) for r in self.query_results]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:top_n]]

    def present_choices(self) -> tuple[RequestData, list[ComicMatch], Path]:
        top_results = self.filter_results()
        best_results: list[ComicMatch] = [
            {
                "title": str(r["name"]),
                "series": str(r["volume"]["name"]),
                "year": int(str(r["cover_date"])[4:]),
                "number": int(r["issue_number"]),
                "cover_link": str(r["image"]["small_url"]),
                "description": str(r["description"]),
                "id": int(r["id"]),
            }
            for r in top_results
        ]
        return (self.expected_info, best_results, self.filepath)

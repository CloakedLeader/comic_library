from collections.abc import Iterator
from dataclasses import dataclass

from my_project.classes.helper_classes import ComicVineIssueStruct, VolumeInfo


@dataclass
class VolumeCandidate:
    volume: VolumeInfo
    matched_queries: set[str]


@dataclass
class Queries:
    combined: str
    title: str
    series: str

    def __iter__(self) -> Iterator[str]:
        seen = set()

        for query in (self.combined, self.title, self.series):
            if query is not None and query not in seen:
                seen.add(query)
                yield query


@dataclass
class Candidate:
    issue: ComicVineIssueStruct
    name: str
    title_score: float | None
    series_score: float
    year_score: float
    image_score: float | None = None

    @property
    def metadata_score(self) -> float:
        scores = [
            (self.series_score, 0.4),
            (self.title_score, 0.4),
            (self.year_score, 0.2),
        ]

        available = [(score, weight) for score, weight in scores if score is not None]

        total_weight = sum(weight for _, weight in available)
        return sum(score * weight for score, weight in available) / total_weight

    @property
    def confidence_score(self) -> float:
        if self.image_score is None:
            raise ValueError("Image score has not been calculated")
        return 0.3 * self.metadata_score + 0.7 * self.image_score

    def __repr__(self) -> str:
        return f"""
        name: {self.name}
        year_score: {self.year_score}
        title_score: {self.title_score}
        series_score: {self.series_score}
        metadata_score = {self.metadata_score}
        image_score = {self.image_score}
        total_score = {self.confidence_score}
            """

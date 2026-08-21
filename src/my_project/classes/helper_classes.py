from collections.abc import Iterable, Iterator
from enum import Enum
from pathlib import Path
from typing import Generic, Optional, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict


class ComicInfo(BaseModel):
    primary_key: str
    filepath: Path
    original_filename: Optional[str] = None
    title: Optional[str] = None
    series: Optional[str] = None
    volume_num: Optional[int] = None
    issue_num: Optional[int] = None
    publisher: Optional[str] = None
    publisher_id: Optional[int] = None
    collection_type: Optional[int] = None
    month: Optional[int] = None
    year: Optional[int] = None
    date: Optional[str] = None
    description: Optional[str] = None
    creators: Optional[list[tuple[str, str]]] = None
    characters: Optional[list[str]] = None
    teams: Optional[list[str]] = None


class GUIComicInfo(BaseModel):
    primary_id: str
    title: str
    filepath: Path
    cover_path: Path


class RSSComicInfo(BaseModel):
    url: str
    title: str
    cover_url: str


class ReviewData(BaseModel):
    iteration: int
    review: str
    date: str


class MetadataInfo(BaseModel):
    primary_id: str
    title: str
    series: str
    volume_num: int
    publisher: str
    date: str
    description: str
    creators: list[tuple[str, list[str]]]
    characters: list[str]
    teams: list[str]
    rating: int
    reviews: list[ReviewData]
    favourite: bool


class ImageInfo(BaseModel):
    icon_url: Optional[str] = None
    medium_url: str
    screen_url: str
    screen_large_url: Optional[str] = None
    small_url: str
    super_url: Optional[str] = None
    thumb_url: str
    tiny_url: str
    original_url: Optional[str] = None
    image_tags: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class Publisher(BaseModel):
    api_detail_url: Optional[str] = None
    id: Optional[int] = None
    name: str

    model_config = ConfigDict(extra="allow")


class ComicVineSearchStruct(BaseModel):
    api_detail_url: Optional[str] = None
    count_of_issues: Optional[int] = None
    date_added: str
    image: Optional[ImageInfo] = None
    publisher: Publisher
    id: int
    name: str
    site_detail_url: Optional[str] = None
    resource_type: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class APISearchResults(BaseModel):
    error: str
    limit: int
    offset: int
    number_of_page_results: int
    number_of_total_results: int
    status_code: int
    results: list[ComicVineSearchStruct]


class CharacterInfo(BaseModel):
    api_detail_url: Optional[str] = None
    id: Optional[int] = None
    name: str
    site_detail_url: Optional[str] = None


class PersonInfo(BaseModel):
    api_detail_url: Optional[str] = None
    id: Optional[int] = None
    name: str
    site_detail_url: Optional[str] = None
    role: str


class VolumeInfo(BaseModel):
    api_detail_url: Optional[str] = None
    id: int
    name: str
    site_detail_url: Optional[str] = None


class TeamInfo(BaseModel):
    api_detail_url: Optional[str] = None
    id: int
    name: str
    site_detail_url: Optional[str] = None


class ComicVineIssueStruct(BaseModel):
    api_detail_url: str
    cover_date: str
    date_added: str
    description: Optional[str] = None
    id: int
    image: ImageInfo
    issue_number: int
    name: Optional[str] = None
    site_detail_url: Optional[str] = None
    store_date: Optional[str] = None
    volume: VolumeInfo


class APIIssueResults(BaseModel):
    error: str
    limit: int
    offset: int
    number_of_page_results: int
    number_of_total_results: int
    status_code: int
    results: list[ComicVineIssueStruct]


class ComicVineDetailStruct(BaseModel):
    api_detail_url: str
    character_credits: list[CharacterInfo]
    cover_date: str
    date_added: str
    description: Optional[str] = None
    id: int
    image: ImageInfo
    issue_number: int
    name: str
    person_credits: list[PersonInfo]
    team_credits: list[TeamInfo]
    volume: VolumeInfo


class HasId(Protocol):
    id: int


T = TypeVar("T", bound=HasId)


class IdSet(Generic[T]):
    def __init__(self, items: Iterable[T] = ()) -> None:
        self._items: dict[int, T] = {}

        for item in items:
            self.add(item)

    def add(self, item: T) -> None:
        self._items.setdefault(item.id, item)

    def extend(self, items: Iterable[T]) -> None:
        for i in items:
            self.add(i)

    def __contains__(self, id: int) -> bool:
        return id in self._items

    def __iter__(self) -> Iterator[T]:
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def get(self, id: int) -> Optional[T]:
        return self._items.get(id)


class MainViewType(Enum):
    GRID_VIEW = "grid_view"
    HOME_VIEW = "home_view"

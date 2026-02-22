from pathlib import Path
from typing import Optional, Sequence

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


class MetadataInfo(BaseModel):
    primary_id: str
    name: str
    volume_num: int
    publisher: str
    date: str
    description: str
    creators: list[tuple[str, list[str]]]
    characters: list[str]
    teams: list[str]
    rating: Optional[int]
    reviews: Sequence[tuple[Optional[str], Optional[str], Optional[int]]]


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
    api_detail_url: Optional[str] = None
    character_credits: Optional[list[CharacterInfo]] = None
    cover_date: str
    date_added: str
    description: Optional[str] = None
    id: int
    image: ImageInfo
    issue_number: int
    name: Optional[str] = None
    person_credits: Optional[list[PersonInfo]] = None
    site_detail_url: Optional[str] = None
    team_credits: Optional[list[TeamInfo]] = None
    volume: VolumeInfo


class APIIssueResults(BaseModel):
    error: str
    limit: int
    offset: int
    number_of_page_results: int
    number_of_total_results: int
    status_code: int
    results: list[ComicVineIssueStruct]

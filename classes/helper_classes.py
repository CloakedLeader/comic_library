from typing import Optional
from pathlib import Path

from pydantic import BaseModel


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
    reviews: list[tuple[Optional[str], Optional[str], Optional[int]]]

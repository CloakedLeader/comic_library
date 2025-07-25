from typing import Optional

from pydantic import BaseModel


class ComicInfo(BaseModel):
    primary_key: str
    filepath: str
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
    filepath: str
    cover_link: Optional[str] = None
    cover_path: Optional[str] = None


class RSSComicInfo(BaseModel):
    url: str
    title: str
    cover_url: str

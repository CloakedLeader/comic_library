from typing import Optional

from pydantic import BaseModel


class ComicInfo(BaseModel):
    primary_key: str
    filepath: str
    original_filename: str
    title: Optional[str] = None
    series: Optional[str] = None
    volume_num: Optional[int] = None
    publisher: Optional[str] = None
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
    cover_link: Optional[str]

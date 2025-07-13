from typing import NotRequired, TypedDict


class ComicInfo(TypedDict):
    title: str
    series: str
    volume_num: int
    publisher: str
    month: int
    year: int
    filepath: str
    description: str
    creators: list[tuple]
    characters: list[str]
    teams: list[str]


class GUIComicInfo(TypedDict):
    primary_id: str
    title: str
    filepath: str
    cover_link: NotRequired[str]

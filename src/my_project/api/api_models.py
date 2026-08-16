from pydantic import BaseModel

from my_project.classes.helper_classes import MetadataInfo


class BasicComicResponse(BaseModel):
    primary_id: str
    title: str
    cover_url: str
    download_url: str


class ComicMetadataResponse(BaseModel):
    primary_id: str
    download_url: str
    cover_url: str
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
    favourite: bool

    @classmethod
    def from_metadata(
        cls,
        metadata: MetadataInfo,
    ) -> "ComicMetadataResponse":
        return cls(
            primary_id=metadata.primary_id,
            download_url=f"/comics/{metadata.primary_id}/download",
            cover_url=f"/comics/{metadata.primary_id}/cover?size=b",
            title=metadata.title,
            series=metadata.series,
            volume_num=metadata.volume_num,
            publisher=metadata.publisher,
            date=metadata.date,
            description=metadata.description,
            creators=metadata.creators,
            characters=metadata.characters,
            teams=metadata.teams,
            rating=metadata.rating,
            favourite=metadata.favourite,
        )

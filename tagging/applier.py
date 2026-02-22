import logging
from datetime import datetime
from pathlib import Path

from classes.helper_classes import (
    CharacterInfo,
    ComicInfo,
    ComicVineIssueStruct,
    PersonInfo,
    Publisher,
    TeamInfo,
)

logging.basicConfig(
    filename="debug.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


class TagApplication:
    def __init__(
        self,
        comicvine_info: ComicVineIssueStruct,
        publisher_info: Publisher,
        api_key: str,
        filename: str,
    ):
        """
        Intialise a TagApplication from a ComicVine-style entry that had been cleaned
        after an API request.

        Args:
            comicvine_dict (dict | list): A ComicVine-style entry or list thereof.
            api_key (str): API key to append to subsequent API requests.
            filename (str): The comic filename, later used to embed metadata.
            session (_type_): HTTP session or client used for network requests; kept
            for use by instance methods.
        """

        self.publisher_info = publisher_info
        self.info = comicvine_info
        self.api_key = api_key
        self.filename = filename

    def create_metadata_dict(self) -> ComicInfo:
        """
        Constructs a metadata dictionary for the current issue from the instance
        issue data.

        Raises:
            ValueError: If issue_data is None.

        Returns:
            dict: Metadata mapping containing keys such as 'Title', 'Series', etc.
        """
        date_str = self.info.cover_date
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        year = date_obj.year
        month = date_obj.month

        information = ComicInfo(
            primary_key="temp",
            filepath=Path("temp"),
            original_filename=self.filename,
            title=self.info.name,
            series=self.info.volume.name,
            volume_num=self.info.issue_number,
            publisher=self.publisher_info.name,
            month=month,
            year=year,
            description=self.info.description,
            characters=self.character_or_team_parsing(self.info.character_credits),
            teams=self.character_or_team_parsing(self.info.team_credits),
            creators=self.creators_entry_parsing(self.info.person_credits or []),
        )
        return information

    @staticmethod
    def creators_entry_parsing(
        list_of_creator_info: list[PersonInfo],
    ) -> list[tuple[str, str]]:
        """
        Aggregate creator credits into a mapping of standard role keys to comma-seperated
        names.

        Args:
            list_of_creator_info (list[dict]): A list of creator entries where each entry
                contains at least the keys "name" and "role".

        Returns:
            dict[str, str]: A dictionary with keys "Penciller", "Writer" etc. Each value is
                a comma-seperated string of names for that role. Or an empty string if there
                are no assigned creators for that role.
        """
        mapping = {
            "penciler": "Penciller",
            "writer": "Writer",
            "inker": "Inker",
            "editor": "Editor",
            "letterer": "Letterer",
            "cover": "CoverArtist",
            "colorist": "Colorist",
            "artist": "Penciller",
        }
        creator_list: list[tuple[str, str]] = []
        for creator in list_of_creator_info:
            creator_list.append((creator.name, mapping[creator.role]))
        return creator_list

    @staticmethod
    def character_or_team_parsing(
        list_of_info: list[TeamInfo] | list[CharacterInfo] | None,
    ) -> list[str]:
        """
        Extract the 'name' field from each character or team entry.

        Args:
            list_of_info (list[dict]): Sequence of dictionaries representing characters
                or teams. Each dictionary is expected to contain the "name" key.

        Returns:
            list[str]: A list of names (as strings) taken from each entry's "name"
                field.
        """
        if list_of_info is None:
            return []
        return [i.name for i in list_of_info]

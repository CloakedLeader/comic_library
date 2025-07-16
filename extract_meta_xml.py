import tempfile
import zipfile
from defusedxml import ElementTree as ET
import os
from typing import Any
from helper_classes import ComicInfo


class MetadataExtraction:
    def __init__(self, path: str, temp_dir: str | None = None) -> None:
        self.filepath: str = path
        self.temp_dir: str = temp_dir if temp_dir else tempfile.mkdtemp()
        self.extracted: bool = False
        self.metadata_root = None

    def extract(self) -> None:
        if not self.extracted:
            with zipfile.ZipFile(self.filepath, "r") as zip_ref:
                zip_ref.extractall(self.temp_dir)
            self.extracted = True

    def get_metadata(self) -> bool:
        """
        Extracts the ComicInfo.xml metadata file from an archive.

        Returns:
            True if the ComicInfo was found, else False.

        Raises:
            zipfile.BadZipFile: If the file is not a valid ZIP archive.
            FileNotFoundError: If the file is not found.
            KeyError: If ComicInfo.xml is not found in the archive.
            ET.ParseError: If ComicInfo.xml is not valid XML.
            Any other exceptions encountered during file access/parsing.
        """
        self.extract()
        if self.metadata_root is not None:
            return True
        xml_path = os.path.join(self.temp_dir, "ComicInfo.xml")
        if os.path.exists(xml_path):
            tree = ET.parse(xml_path)
            self.metadata_root = tree.getroot()
            return True
        else:
            return False

    def has_complete_metadata(self, required: list) -> bool:
        """
        Checks that the required metadata fields are complete with some info
        e.g. that they are not blank.

        Args:
        required: A list of the fields that must be present.

        Returns:
        True if all required info is present, else False.
        """
        for field in required:
            try:
                self.get_text(field)
            except KeyError:
                return False
        return True

    def get_text(self, tag: str) -> str:
        """
        Searches for results under the tag given. Returns the stripped content.

        Args:
            tag: The section to search for (e.g. writer, summary etc).

        Returns:
            The stripped text from the tag.

        Raises:
            KeyError: If the tag is missing or has no text content.
        """
        element = self.metadata_root.find(tag)
        if element is not None and element.text:
            return element.text.strip()
        else:
            raise KeyError(f"No info inside tag: {tag}.")

    def easy_parsing(self, field: str, as_type: type = str) -> str | int:
        """
        Returns metadata from the corresponding field by parsing an XML tree.
        Assumes ComicInfo.xml has already been verified to exist and be readable.

        Args:
        field: The name of the metadata field.
        as_type: The type that the metadata must be returned as.
            Required as all metadata fields are strings by default
            but some must be integers.

        Returns:
        The metadata inside that field, either a string or integer.
        Never type None.
        """
        text = self.get_text(field)
        if text is None:
            raise KeyError(f"Field '{field}' not found in metadata.")

        try:
            return as_type(text)
        except ValueError as e:
            raise TypeError(
                f"Could not convert field '{field}' to {as_type.__name__}"
            ) from e

    def parse_characters_or_teams(self, field: str) -> list[str]:
        """
        Finds all the characters or teams affliated with the comic book.

        Args:
        field: Whether to search under the characters or teams field.

        Returns:
        A list of the corresponding people.
        """
        seen = set()
        out = []
        list_string = self.easy_parsing(field)
        items = [p.strip() for p in list_string.split(",")]
        for item in items:
            if item not in seen:
                seen.add(item)
                out.append(item)

        return out

    def parse_creators(self, fields: list) -> list[tuple]:
        """
        Finds all the creators affliated with the book.

        Args:
        fields: A list of job titles of the creator(s) for example:
            'Writer' or 'Penciller'

        Returns:
        A list of tuples of people and their role, for example:
        (John Byrne, Penciller)
        """
        creator_role_list = []
        seen_per_role = {field: set() for field in fields}
        for field in fields:
            list_string = self.easy_parsing(field)
            people_raw = [p.strip() for p in list_string.split(",")]
            for person in people_raw:
                if person not in seen_per_role[field]:
                    seen_per_role[field].add(person)
                    creator_role_list.append((person, field))
        return creator_role_list

    def to_dict(self) -> dict[str, Any]:
        roles = ["Writer", "Penciller", "CoverArtist",
                 "Inker", "Colorist", "Letterer", "Editor"]
        final_dict: ComicInfo = {
            "title": self.easy_parsing("Title"),
            "series": self.easy_parsing("Series"),
            "volume_num": self.easy_parsing("Number", int),
            "publisher": self.easy_parsing("Publisher"),
            "month": self.easy_parsing("Month", int),
            "year": self.easy_parsing("Year", int),
            "file_path": self.filepath,
            "description": self.easy_parsing("Summary"),
            "creators": self.parse_creators(roles),
            "characters": self.parse_characters_or_teams("Characters"),
            "teams": self.parse_characters_or_teams("Teams")
        }
        return final_dict

    def extract_metadata(self) -> dict[str, Any]:
        required_fields = ["Title", "Series", "Year", "Number", "Writer", "Summary"]
        self.extract()
        if self.has_complete_metadata(required_fields):
            return self.to_dict()

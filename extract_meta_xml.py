import os
import shutil
import tempfile
import zipfile

from defusedxml import ElementTree as ET

from helper_classes import ComicInfo


class MetadataExtraction:
    def __init__(self, comic_info: ComicInfo) -> None:
        self.comic_info = comic_info
        self.filepath: str = comic_info.filepath
        self.temp_dir: str = tempfile.mkdtemp()
        self.extracted: bool = False
        self.metadata_root = None

    def __enter__(self):
        self.extract()
        self.get_metadata()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.cleanup()

    def extract(self) -> None:
        if not self.extracted:
            with zipfile.ZipFile(self.filepath, "r") as zip_ref:
                zip_ref.extractall(self.temp_dir)
            self.extracted = True

    def get_metadata(self) -> None:
        """
        Extracts the ComicInfo.xml metadata file from an archive.

        Raises:
            zipfile.BadZipFile: If the file is not a valid ZIP archive.
            FileNotFoundError: If the file is not found.
            KeyError: If ComicInfo.xml is not found in the archive.
            ET.ParseError: If ComicInfo.xml is not valid XML.
            Any other exceptions encountered during file access/parsing.
        """
        self.extract()
        if self.metadata_root is not None:
            return
        xml_path = os.path.join(self.temp_dir, "ComicInfo.xml")
        if os.path.exists(xml_path):
            tree = ET.parse(xml_path)
            self.metadata_root = tree.getroot()

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
        if self.metadata_root is None:
            raise ValueError("metadata_root has not been intialised.")
        element = self.metadata_root.find(tag)
        if element is not None and element.text:
            return element.text.strip()
        else:
            if tag in [
                "Editor",
                "Letterer",
                "Inker",
                "Colorist",
                "CoverArtist",
                "Teams",
            ]:
                return ""
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
        if list_string == "":
            return []
        if isinstance(list_string, str):
            items = [p.strip() for p in list_string.split(",")]
        else:
            raise ValueError("Not a valid tag in the xml tree.")
        for item in items:
            if item not in seen:
                seen.add(item)
                out.append(item)

        return out

    def parse_creators(self, fields: list) -> list[tuple[str, str]]:
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
        seen_per_role: dict[str, set] = {field: set() for field in fields}
        for field in fields:
            list_string = self.easy_parsing(field, str)
            if list_string == "":
                continue
            if isinstance(list_string, str):
                people_raw = [p.strip() for p in list_string.split(",")]
            else:
                raise ValueError("Not a correct field in the xml.")
            for person in people_raw:
                if person not in seen_per_role[field]:
                    seen_per_role[field].add(person)
                    creator_role_list.append((person, field))
        return creator_role_list

    def cleanup(self) -> None:
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def run(self) -> ComicInfo:
        roles = [
            "Writer",
            "Penciller",
            "CoverArtist",
            "Inker",
            "Colorist",
            "Letterer",
            "Editor",
        ]
        updates = {
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
            "teams": self.parse_characters_or_teams("Teams"),
        }
        final_info = self.comic_info.model_copy(update=updates)
        self.cleanup()
        print(final_info)
        return final_info

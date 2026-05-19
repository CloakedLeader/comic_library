"""
A class to create a XML formatted file and replace any missing data with
certain flags depending on whether they are necessary or just optional.

Also ensures that duplicate `ComicInfo.xml` files are not inserted into
comic archives by extracting and re-packaging comic archive files.
"""

import os
import xml.etree.ElementTree as ET  # nosec
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from classes.helper_classes import ComicInfo


class XMLStruc(BaseModel):
    """
    A data structure for data inputted into the `ComicInfo.xml`.

    All data are either strings or integers so they can be nicely
    inputted into the file.

    Everything execept the writer credits are neccessary because the
    writer credits are added at a later time.

    Empty entries are then inputted as empty strings "".
    Integer entries must not be empty.
    """

    Title: str
    Series: str
    Number: int
    Publisher: str
    Month: int
    Year: int
    Summary: str
    Characters: str
    Teams: str
    Penciller: Optional[str] = None
    Writer: Optional[str] = None
    Inker: Optional[str] = None
    Editor: Optional[str] = None
    Letterer: Optional[str] = None
    CoverArtist: Optional[str] = None
    Colorist: Optional[str] = None


class MetadataInserter:
    """
    Manages the insertion of metadata into embedded XML file in the comic archive.

    Attributes:

        info (ComicInfo): A ComicInfo struct containing the metadata from scraping.
            It has been cleaned ready for insertion but just needs to be formatted
            slightly differently.

        path (Path): The filepath of the comic so that the XML can be written to
            it.

        pending (bool): A boolean to track some fields which are mandatory are missing.
            Edited in place to True if all the required entries are in place.

        information (XMLStruc): The created data structure that is edited in place
            as the process runs.
    """

    def __init__(self, clean_info: ComicInfo, filepath: Path):
        """
        Initialises the instance variables.

        Args:
            clean_info (ComicInfo): The cleaned ComicInfo struct.
            filepath (Path): The filepath of the comic.
        """
        self.info = clean_info
        self.path = filepath
        self.pending = False

    def create_valid_struc(self) -> bool:
        """
        Attemps to create a :class`XMLStruc` with the information
        in `self.info`.

        Any gaps are then filled and the inverted pending status
        returned.

        Returns:
            bool: True if there are no missing required fields.
                False if there are.
        """
        information = XMLStruc(
            Title=self.info.title or "",
            Series=self.info.series or "",
            Number=self.info.volume_num or self.info.issue_num or 1,
            Publisher=self.info.publisher or "",
            Month=self.info.month or 0,
            Year=self.info.year or 0,
            Summary=self.info.description or "",
            Characters=", ".join(self.info.characters or []),
            Teams=", ".join(self.info.teams or []),
        )

        information = information.model_copy(
            update=self.creators_parsing(self.info.creators or [])
        )
        self.information = self.fill_gaps(information)
        return not self.pending

    def create_xml(self) -> bytes:
        """
        Takes the data in `self.information` and turns it into the root
        element of an XML file.

        Returns:
            bytes: The bytes representation of the XML file.
        """
        root = ET.Element("ComicInfo")

        for key, value in self.information.model_dump().items():
            child = ET.SubElement(root, key)
            child.text = str(value)

        xml_bytes = BytesIO()
        tree = ET.ElementTree(root)
        tree.write(xml_bytes, encoding="utf-8", xml_declaration=True)
        return xml_bytes.getvalue()

    def insert_xml(self, xml_bytes: bytes) -> None:
        """
        Inserts the XML file into the comic archive.

        Args:
            xml_bytes (bytes): The bytes of the XML file to insert.
        """
        with zipfile.ZipFile(self.path, "a") as cbz:
            cbz.writestr("ComicInfo.xml", xml_bytes)

    def already_has_xml(self) -> bool:
        """
        Checks if an instance of `ComicInfo.xml` already exists in
        the archive.

        This prevents duplicating the file and avoids errors for future
        taggers not knowing which version to use.

        Returns:
            bool: True if there is already one, False otherwise.
        """
        with zipfile.ZipFile(self.path, "r") as cbz:
            return "ComicInfo.xml" in cbz.namelist()

    @staticmethod
    def creators_parsing(creators: list[tuple[str, str]]) -> dict[str, str]:
        """
        Sorts the creators into their different jobs/roles.

        Goes through a list of tuples, one for each creator-role pair and unpacks them
        into each of the different roles. Also capitalises the role names so they are
        uniform with XML structure.

        Args:
            creators (list[tuple[str, str]]): A list of tuples, each of which has the
            format `(person, role)` where both a role and a person can appear multiple
            times in the list.

        Returns:
            dict[str, str]: A dictionary where the keys are the role titles and the values
            are strings of names separated by commas and then a space.
        """
        mapping_ = {
            "penciler": "Penciller",
            "writer": "Writer",
            "inker": "Inker",
            "editor": "Editor",
            "letterer": "Letterer",
            "cover": "CoverArtist",
            "colorist": "Colorist",
            "artist": "Penciller",
        }
        dummy_creator_dict: dict[str, list[str]] = {
            "Penciller": [],
            "Writer": [],
            "Inker": [],
            "Editor": [],
            "Letterer": [],
            "CoverArtist": [],
            "Colorist": [],
        }
        creator_dict: dict[str, str] = {}

        for person, role in creators:
            if role is None:
                continue
            roles = [r.strip() for r in role.split(",")]
            for role in roles:
                if role in dummy_creator_dict.keys():
                    dummy_creator_dict[role].append(person)
                elif role in mapping_.keys():
                    role_real = mapping_[role]
                    dummy_creator_dict[role_real].append(person)

        for title, names in dummy_creator_dict.items():
            creator_dict[title] = ", ".join(names)

        return creator_dict

    def fill_gaps(self, comic_info: XMLStruc) -> XMLStruc:
        """
        Fills the gaps in the :class`XMLStruc` with 'PENDING' for required
        entries and 'MISSING' for entries that are missing but not essential.

        Args:
            comic_info (XMLStruc): The filled in :class`XMLStruc`.

        Returns:
            XMLStruc: The completed :class`XMLStruc` that has the empty fields
            replaced with the relevant string marker.
        """
        MANDATORY_FIELDS = {
            "Writer",
            "Penciller",
            "Year",
            "Summary",
            "Number",
            "Series",
            "Title",
        }

        data = comic_info.model_dump()

        for field in MANDATORY_FIELDS:
            if field not in data or not data[field]:
                data[field] = "PENDING"
                self.pending = True
        for key in list(data.keys()):
            if key not in MANDATORY_FIELDS and not data[key]:
                data[key] = "MISSING"

        return comic_info.model_copy(update=data)

    def replace_xml(self, xml_bytes: bytes) -> None:
        """
        Replaces the `ComicInfo.xml` file from a comic archive.

        Extracts the archive into a temporary file, removes the old
        files and adds the new one. Then re-packages the file back
        into a comic archive.

        Args:
            xml_bytes (bytes): The bytes of the XML file to insert.
        """
        temp_path = self.path.with_suffix(".tmp")
        try:
            with (
                zipfile.ZipFile(self.path, "r") as zin,
                zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as zout,
            ):
                for item in zin.infolist():
                    if item.filename != "ComicInfo.xml":
                        zout.writestr(item, zin.read(item.filename))
                zout.writestr("ComicInfo.xml", xml_bytes)

            os.replace(temp_path, self.path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise

    def run_inserter(self) -> None:
        """Basic flow for running the process of inserting `ComicInfo.xml"""
        xml = self.create_xml()

        if self.already_has_xml():
            self.replace_xml(xml)
        else:
            self.insert_xml(xml)

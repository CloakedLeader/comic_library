import logging
import xml.etree.ElementTree as ET  # nosec
import zipfile
from io import BytesIO
from pathlib import Path

from classes.helper_classes import ComicInfo


class MetadataInserter:
    def __init__(self, clean_info: ComicInfo, filepath: Path):
        self.info = clean_info
        self.path = filepath

    def insert_xml(self):
        information: dict[str, str | int] = {
            "Title": self.info.title or "",
            "Series": self.info.series or "",
            "Number": self.info.volume_num or self.info.issue_num or 1,
            "Publisher": self.info.publisher or "",
            "Month": self.info.month or 0,
            "Year": self.info.year or 0,
            "Summary": self.info.description or "",
            "Characters": ", ".join(self.info.characters or []),
            "Teams": ", ".join(self.info.teams or []),
        }
        information.update(self.creators_parsing(self.info.creators or []))
        information = self.fill_gaps(information)

        root = ET.Element("ComicInfo")
        for key, value in information.items():
            child = ET.SubElement(root, key)
            child.text = str(value)

        xml_bytes = BytesIO()
        tree = ET.ElementTree(root)
        tree.write(xml_bytes, encoding="utf-8", xml_declaration=True)

        with zipfile.ZipFile(self.path, "a") as cbz:
            cbz.writestr("ComicInfo.xml", xml_bytes.getvalue())

    @staticmethod
    def creators_parsing(creators: list[tuple[str, str]]) -> dict[str, str]:
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

        for title, names in dummy_creator_dict.items():
            creator_dict[title] = ", ".join(names)

        return creator_dict

    @staticmethod
    def fill_gaps(comic_info: dict) -> dict:
        MANDATORY_FIELDS = {
            "Writer",
            "Penciller",
            "Year",
            "Summary",
            "Number",
            "Series",
            "Title",
        }

        for field in MANDATORY_FIELDS:
            if field not in comic_info.keys() or not comic_info[field]:
                comic_info[field] = "PENDING"
        for key in comic_info.keys():
            if key not in MANDATORY_FIELDS and comic_info[key] in (None or ""):
                comic_info[key] = "PENDING"
        return comic_info

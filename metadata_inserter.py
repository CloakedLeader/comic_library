import xml.etree.ElementTree as ET  # nosec
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from classes.helper_classes import ComicInfo


class XMLStruc(BaseModel):
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
    def __init__(self, clean_info: ComicInfo, filepath: Path):
        self.info = clean_info
        self.path = filepath

    def insert_xml(self):
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
        information = self.fill_gaps(information)

        root = ET.Element("ComicInfo")

        for key, value in information.model_dump().items():
            child = ET.SubElement(root, key)
            child.text = str(value)

        xml_bytes = BytesIO()
        tree = ET.ElementTree(root)
        tree.write(xml_bytes, encoding="utf-8", xml_declaration=True)

        if self.has_complete_xml(xml_bytes.getvalue()):
            return

        with zipfile.ZipFile(self.path, "a") as cbz:
            cbz.writestr("ComicInfo.xml", xml_bytes.getvalue())

    def has_complete_xml(self, xml_bytes: bytes) -> bool:
        with zipfile.ZipFile(self.path, "r") as cbz:
            if "ComicInfo.xml" in cbz.namelist():
                content = cbz.read("ComicInfo.xml")
                return self.xml_equal(content, xml_bytes)
            else:
                return False

    @staticmethod
    def xml_equal(a: bytes, b: bytes) -> bool:
        return ET.tostring(ET.fromstring(a)) == ET.tostring(ET.fromstring(b))

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
                elif role in mapping_.keys():
                    role_real = mapping_[role]
                    dummy_creator_dict[role_real].append(person)

        for title, names in dummy_creator_dict.items():
            creator_dict[title] = ", ".join(names)

        return creator_dict

    @staticmethod
    def fill_gaps(comic_info: XMLStruc) -> XMLStruc:
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
        for key in list(data.keys()):
            if key not in MANDATORY_FIELDS and not data[key]:
                data[key] = "MISSING"

        return comic_info.model_copy(update=data)

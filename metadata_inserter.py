import os
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
        self.pending = False

    def create_valid_struc(self) -> bool:
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
        root = ET.Element("ComicInfo")

        for key, value in self.information.model_dump().items():
            child = ET.SubElement(root, key)
            child.text = str(value)

        xml_bytes = BytesIO()
        tree = ET.ElementTree(root)
        tree.write(xml_bytes, encoding="utf-8", xml_declaration=True)
        return xml_bytes.getvalue()

    def insert_xml(self, xml_bytes: bytes) -> None:
        with zipfile.ZipFile(self.path, "a") as cbz:
            cbz.writestr("ComicInfo.xml", xml_bytes)

    def already_has_xml(self) -> bool:
        with zipfile.ZipFile(self.path, "r") as cbz:
            return "ComicInfo.xml" in cbz.namelist()

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

    def fill_gaps(self, comic_info: XMLStruc) -> XMLStruc:
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
        temp_path = self.path.with_suffix(".tmp")
        try:
            with zipfile.ZipFile(self.path, "r") as zin, \
            zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as zout:
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
        xml = self.create_xml()

        if self.already_has_xml():
            self.replace_xml(xml)
        else:
            self.insert_xml(xml)

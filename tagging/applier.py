import xml.etree.ElementTree as ET  # nosec
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests

from classes.helper_classes import ComicInfo
from metadata_cleaning import MetadataProcessing


class TagApplication:
    def __init__(
        self, comicvine_dict: dict | list, api_key: str, filename: str, session
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
        if isinstance(comicvine_dict, list):
            entry = comicvine_dict[0]
        else:
            entry = comicvine_dict
        self.link = entry["api_detail_url"]
        self.issue_id = entry["id"]
        self.volume_id = entry["volume"]["id"]
        self.pub_link = entry["volume"]["api_detail_url"]
        self.api_key = api_key
        self.filename = filename
        self.session = session
        self.url: Optional[str] = None
        self.issue_data = None
        self.final_info: Optional[dict] = None

    def build_url(self) -> None:
        """
        Construct the fully qualified issue-detail URL with required query
        parameters and store it on the instance.
        Sets self.url to the prepared GET URL for self.link including standard
        parameters: API key and format.
        """
        req = requests.Request(
            method="GET",
            url=self.link,
            params={
                "api_key": self.api_key,
                "format": "json",
            },
        )
        prepared = req.prepare()
        self.url = prepared.url

    def get_publisher(self) -> str:
        """
        Fetch the publisher name for the issue's volume using the instance
        volume link.

        Returns:
            str: Publisher name from the API resource.
        """
        url = f"{self.pub_link}?api_key={self.api_key}&format=json"
        response = self.session.get(url)
        data = response.json()
        return data["results"]["publisher"]["name"]

    def get_request(self) -> None:
        """
        Fetches issue data from the prepared API URL and stores the parsed
        results on the instance.
        Ensures the request URL is built before performing HTTP GET.
        Prints a message when the response status is not 200.
        Sets self.issue_data to the responses JSON 'results' entry.

        Raises:
            ValueError: Raises the error if the URL is still None even after
            the function call to expliciting bind it.
        """
        if not self.url:
            self.build_url()
        if self.url is None:
            raise ValueError("url cannot be None")
        response = self.session.get(self.url)
        if response.status_code != 200:
            print(f"Request failed with status code: {response.status_code}")
        data = response.json()
        print(data["results"])
        self.issue_data = data["results"]

    def parse_list_of_dicts(self, field) -> list[str]:
        """
        Extracts the list of 'name' values from a named list field in the
        loaded issue data.

        Args:
            field (str): Key in 'self.issue_data' whose value is a list of dicts
                each containing a '"name"' entry.

        Raises:
            ValueError: If 'self.issue_data' is None.

        Returns:
            list[str]: List of 'name' strings extracted from each dictionary in
                'self.issue_data[field]'.
        """
        if self.issue_data is None:
            raise ValueError("issue_data cannot be None")
        entries = self.issue_data[field]
        things = []
        for entry in entries:
            things.append(entry["name"])
        return things

    def create_metadata_dict(self) -> dict:
        """
        Constructs a metadata dictionary for the current issue from the instance
        issue data.

        Raises:
            ValueError: If issue_data is None.

        Returns:
            dict: Metadata mapping containing keys such as 'Title', 'Series', etc.
        """
        if self.issue_data is None:
            raise ValueError("issue_data cannot be None")
        date_str = self.issue_data["cover_date"]
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        year = date_obj.year
        month = date_obj.month
        simple_info = ComicInfo(
            primary_key="temp",
            filepath=Path("temp"),
            original_filename=self.filename,
            title=self.issue_data["name"],
            series=self.issue_data["volume"]["name"],
            volume_num=self.issue_data["issue_number"],
        )
        processor = MetadataProcessing(simple_info)
        clean_title_info = processor.title_parsing()

        information: dict = {
            "Title": clean_title_info["title"],
            "Series": clean_title_info["series"],
            "Number": clean_title_info["volume_num"],
            "Publisher": self.get_publisher(),
            "Month": month,
            "Year": year,
            "Summary": self.issue_data["description"],
            "Characters": ", ".join(
                self.character_or_team_parsing(self.issue_data["character_credits"])
            ),
            "Teams": ", ".join(
                self.character_or_team_parsing(self.issue_data["team_credits"])
            ),
            "api_link": self.issue_data["api_detail_url"],
        }

        information.update(
            self.creators_entry_parsing(self.issue_data["person_credits"])
        )
        self.final_info = information
        return information

    @staticmethod
    def creators_entry_parsing(list_of_creator_info: list[dict]) -> dict[str, str]:
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
        creator_dict = {v: "" for v in mapping.values()}

        for info in list_of_creator_info:
            roles = [r.strip().lower() for r in info["role"].split(",")]
            for role in roles:
                if role in mapping:
                    key = mapping[role]
                    if creator_dict[key]:
                        creator_dict[key] += ", " + info["name"]
                    else:
                        creator_dict[key] = info["name"]

        return creator_dict

    @staticmethod
    def character_or_team_parsing(list_of_info: list[dict]) -> list[str]:
        """
        Extract the 'name' field from each character or team entry.

        Args:
            list_of_info (list[dict]): Sequence of dictionaries representing characters
                or teams. Each dictionary is expected to contain the "name" key.

        Returns:
            list[str]: A list of names (as strings) taken from each entry's "name"
                field.
        """
        peoples = []
        for i in list_of_info:
            peoples.append(str(i["name"]))
        return peoples

    def fill_gaps(self):
        """
        Ensure required metadata keys exist in self.final_info and replace absent
        or empty values with defaults.
        Mandatory fields are set to "PENDING" when missing or empty.
        All other keys present in self.final_info that are None or empty strings are
        set to "MISSING".

        Modifies self.final_info in place.
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
        if self.final_info is None:
            # Need to add logic here.
            return
        for field in MANDATORY_FIELDS:
            if field not in self.final_info.keys() or not self.final_info[field]:
                self.final_info[field] = "PENDING"
        for key in self.final_info.keys():
            if key not in MANDATORY_FIELDS:
                if self.final_info[key] is (None or ""):
                    self.final_info[key] = "MISSING"

    def create_xml(self) -> bytes:
        """
        Create a ComicInfo XML document from the instance's final metadata and
            return it as bytes.

        Builds an XML document using each value's string representation as element
            text.

        Raises:
            ValueError: If self.final_info is None.

        Returns:
            bytes: UTF-8 encoded XML document including an XML declaration.
        """
        root = ET.Element("ComicInfo")

        if self.final_info is None:
            raise ValueError("final_info cannot be None")
        for key, value in self.final_info.items():
            child = ET.SubElement(root, key)
            child.text = str(value)

        xml_bytes_io = BytesIO()
        tree = ET.ElementTree(root)
        tree.write(xml_bytes_io, encoding="utf-8", xml_declaration=True)
        return xml_bytes_io.getvalue()

    def insert_xml_into_cbz(self, cbz_path: Path):
        """
        Append a generated ComicInfo.xml file into an existing CBZ archive.

        Args:
            cbz_path (Path): Path to an existing CBZ file to which the generated
                ComicInfo.xml will be written.

        Raises:
            FileNotFoundError: If 'cbz_path' does not exist.
        """
        if not cbz_path.exists():
            raise FileNotFoundError(f"{str(cbz_path)} does not exist")
        self.fill_gaps()
        xml_content = self.create_xml()

        with zipfile.ZipFile(str(cbz_path), "a") as cbz:
            cbz.writestr("ComicInfo.xml", xml_content)

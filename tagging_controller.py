import os
import zipfile
from concurrent.futures import ThreadPoolExecutor
from enum import IntEnum
from io import BytesIO
from pathlib import Path
from typing import Optional
import logging

import imagehash
from imagehash import ImageHash
import requests
from dotenv import load_dotenv
from PIL import Image

from tagging.applier import TagApplication
from tagging.lexer import Lexer, LexerFunc, run_lexer
from tagging.parser import Parser
from tagging.requester import HttpRequest, RequestData
from tagging.validator import SearchResponseValidator, IssueResponseValidator
from classes.helper_classes import ComicVineIssueStruct

load_dotenv()
API_KEY = os.getenv("API_KEY")
logging.basicConfig(
    filename="debug.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class MatchCode(IntEnum):
    NO_MATCH = 0
    ONE_MATCH = 1
    MULTIPLE_MATCHES = 2


header = {
    "User-Agent": "AutoComicLibrary/1.0 (contact: adam.perrott@protonmail.com;"
    " github.com/CloakedLeader/comic_library)",
    "Accept": r"*/*",
    "Accept-Encoding": "gzip,deflate,br",
    "Connection": "keep-alive",
}
session = requests.Session()
session.headers.update(header)


class TaggingPipeline:
    def __init__(
        self, data: RequestData, path: Path, size: float, api_key: str
    ) -> None:
        self.data = data
        self.path = path
        self.size = size
        self.http = HttpRequest(data, api_key, session)
        self.cover = self.cover_getter()
        self.coverhashes = self.cover_hasher()
        self.results: list[ComicVineIssueStruct] = []

    def cover_getter(self):
        with zipfile.ZipFile(str(self.path), "r") as zip_ref:
            image_files = [
                f
                for f in zip_ref.namelist()
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if not image_files:
                logging.debug(f"Empty archive in {self.path}")
                raise ValueError("Empty archive.")
                    
            image_files.sort()
            cover = zip_ref.read(image_files[0])
            return BytesIO(cover)

    def cover_hasher(self) -> dict[str, ImageHash]:
        image = Image.open(self.cover)
        return {
            "phash": imagehash.phash(image),
            "dhash": imagehash.dhash(image),
            "ahash": imagehash.average_hash(image),
        }

    def run(self) -> MatchCode:
        queries: list[str] = [
            f"{self.data.series} {self.data.title or ''}".strip(),
            self.data.series,
            self.data.title,
        ]
        self.potential_results: list = []

        skipped_vols = []
        good_matches = []
        for q in queries:

            self.http.build_url_search(q)
            results = self.http.search_get_request()
            self.search_validator = SearchResponseValidator(results.results, self.data)

            print(f"There are {len(results.results)} results returned.")
            filtered_results = self.search_validator.filter_search_results()
            print(
                "After filtering for title, publisher and issue "
                + f"there are {len(filtered_results)} remaining results."
            )

            if len(filtered_results) == 0:
                continue

            vol_info = [(i.id, i.name) for i in filtered_results]
            final_results = []
            for index, (j, k) in enumerate(vol_info):
                self.http.build_url_iss(j)
                issue_results = self.http.issue_get_request()

                self.issue_validator = IssueResponseValidator(issue_results.results, self.data)
                logging.debug(
                    f"There are {len(self.issue_validator.results)}"
                    + f" issues in the matching volume: '{k}' for query {q}."
                )
                temp_results = self.issue_validator.filter_issue_results()

                logging.debug(
                    "After filtering for title and year "
                    + f"there are {len(temp_results)} results remaining for query {q}"
                )

                if len(temp_results) == 0:
                    continue

                if len(temp_results) > 25:
                    logging.debug(
                        "Too many issues to compare covers, "
                        + f"skipping volume '{k}'."
                    )
                    skipped_vols.append((j, k, len(temp_results)))
                    continue

                self.potential_results.extend(temp_results)
                self.issue_validator.cover_img_url_getter()
                images: list[BytesIO] = []
                with ThreadPoolExecutor(max_workers=5) as executor:
                    images = list(executor.map(
                            self.http.download_img, self.issue_validator.urls))

                for index, i in enumerate(images):
                    try:
                        score = self.issue_validator.cover_img_comp_w_weight(
                            self.coverhashes, i
                        )
                        logging.debug(f"Index {index}: similarity score = {score:.2f}")
                        if score > 0.85:
                            final_results.append(temp_results[index])
                    except Exception as e:
                        logging.error(f"Error comparing image at index {index}: {e}.")
                good_matches.extend(final_results)

            if len(final_results) == 1:
                logging.info(final_results[0].volume.name)
                logging.info("There is ONE match!!!")
                logging.info(good_matches)
                self.results.extend(final_results)
                self.publisher_info = self.search_validator.get_publisher_info(final_results[0].volume.id)
                break
            elif len(final_results) == 0:
                logging.warning(f"There are no matches using query {q}.")
                continue
            elif len(final_results) > 1:
                for res in good_matches:
                    logging.debug(res.volume.name)
                self.results.extend(final_results)
                continue
                # Need to use scoring or sorting or closest title match etc.
                # If that cant decide then we need to flag the comic
                # and ask the user for input.
        if len(self.results) == 0:
            logging.warning("There are no matches")
            return MatchCode.NO_MATCH
        elif len(self.results) > 1:
            logging.warning("There are multiple matches")
            return MatchCode.MULTIPLE_MATCHES
        else:
            return MatchCode.NO_MATCH


def run_tagging_process(filepath: Path, api_key: str) -> Optional[tuple[list, RequestData]]:
    filename = filepath.stem
    lexer_instance = Lexer(filename)
    state: Optional[LexerFunc] = run_lexer
    while state is not None:
        state = state(lexer_instance)
    parser_instance = Parser(lexer_instance.items)
    comic_info = parser_instance.parse()
    logging.debug(f"The filename {filename} gives the following info:\n", comic_info)
    series = comic_info.series
    num = comic_info.volume_number
    year = comic_info.year
    title = comic_info.title

    data = RequestData(num, year, series, title)

    tagger = TaggingPipeline(data=data, path=filepath, size=filepath.stat().st_size, api_key=api_key)

    final_result = tagger.run()
    if final_result == MatchCode.ONE_MATCH:
        inserter = TagApplication(tagger.results[0], tagger.publisher_info, api_key, filename, session)
        inserter.create_metadata_dict()
        inserter.insert_xml_into_cbz(filepath)
        return None
    elif final_result == MatchCode.NO_MATCH:
        return (tagger.potential_results, tagger.data)
        print("Need another method to find matches")
        best_matches = tagger.filtered_for_none
        return (best_matches, tagger.data)
        # Add a method to rank and return the best 3-5 matches.
    elif final_result == MatchCode.MULTIPLE_MATCHES:
        return (tagger.results, tagger.data)
        print("Multiple matches, require user input to disambiguate.")
        best_matches = tagger.filtered_for_many
        return (best_matches, tagger.data)
        # Need to create a gui popup to allow user to select correct match.
    else:
        raise ValueError("Something has gone wrong")


def extract_and_insert(match, api_key, filename: str, filepath: Path):
    inserter = TagApplication(match, api_key, filename, session)
    inserter.get_request()
    inserter.create_metadata_dict()
    inserter.insert_xml_into_cbz(filepath)
    return None

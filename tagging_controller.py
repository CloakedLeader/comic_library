import os
import xml.etree.ElementTree as ET  # nosec
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import IntEnum
from io import BytesIO
from pathlib import Path
from typing import Optional
import imagehash
import requests
from dotenv import load_dotenv
from PIL import Image

from comic_match_logic import ResultsFilter
from tagging.requester import RequestData
from tagging.requester import HttpRequest
from tagging.validator import ResponseValidator
from tagging.applier import TagApplication
from tagging.parser import Parser
from tagging.lexer import Lexer, run_lexer, LexerFunc

load_dotenv()
API_KEY = os.getenv("API_KEY")


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
    def __init__(self, data: RequestData, path: Path, size: float, api_key: str) -> None:
        """
        Initialise a tagging pipeline for the given CBZ file, preparing HTTP access, cover image and perceptual hashes.
        
        Parameters:
            data (RequestData): Parsed metadata to use for searches and matching.
            path (Path): Filesystem path to the CBZ archive to process.
            size (float): Reference size value used by similarity/selection heuristics.
            api_key (str): API key used to construct the HTTP client.
        
        Notes:
            Sets up an HttpRequest using the shared session, initialises the validator to None, extracts the archive's cover image and computes its `phash`, `dhash` and `ahash`, and initialises an empty `results` list.
        """
        self.data = data
        self.path = path
        self.size = size
        self.http = HttpRequest(data, api_key, session)
        self.validator = None
        self.cover = self.cover_getter()
        self.coverhashes = self.cover_hasher()
        # dictionary of (phash, dhash, ahash)
        self.results: list[dict] = []

    def cover_getter(self):
        with zipfile.ZipFile(str(self.path), "r") as zip_ref:
            image_files = [
                f
                for f in zip_ref.namelist()
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if not image_files:
                print("Empty archive.")
                return
            image_files.sort()
            cover = zip_ref.read(image_files[0])
            return BytesIO(cover)

    def cover_hasher(self):
        image = Image.open(self.cover)
        return {
            "phash": imagehash.phash(image),
            "dhash": imagehash.dhash(image),
            "ahash": imagehash.average_hash(image),
        }

    def run(self):
        """
        Search for matching volumes on ComicVine and compare cover images to identify matches.
        
        Performs a series of search queries derived from the stored request data, filters results by issue count,
        publisher, year and title, downloads candidate cover images and compares them to the archive's cover.
        Populates self.results with any confirmed matches.
        
        Returns:
            If exactly one confirmed match is found, `MatchCode.ONE_MATCH`.
            If no confirmed matches are found, `(MatchCode.NO_MATCH, potential_results)` where `potential_results` is a list of candidate issue dictionaries considered.
            If multiple confirmed matches are found, `(MatchCode.MULTIPLE_MATCHES, results)` where `results` is the list of matching issue dictionaries.
        """
        queries = [
            f"{self.data.series} {self.data.title or ''}".strip(),
            self.data.series,
            self.data.title,
        ]
        potential_results = []

        skipped_vols = []
        for q in queries:
            good_matches = []

            self.http.build_url_search(q)
            results = self.http.get_request("search")
            self.validator = ResponseValidator(results, self.data)

            print(f"There are {len(results['results'])} results returned.")
            results = self.validator.issue_count_filter()
            self.validator.results = results
            results = self.validator.pick_best_volumes(number=8)
            self.validator.results = results
            results = self.validator.pub_checker(results)
            self.validator.results = results
            print(
                "After filtering for title, publisher and issue "
                + f"there are {len(results)} remaining results."
            )
            final_results = results

            if len(final_results) == 0:
                continue

            vol_info = []
            for i in final_results:
                id = i["id"]
                name = i["name"]
                vol_info.append((id, name))
            for index, (j, k) in enumerate(vol_info):
                self.http.build_url_iss(j)
                temp_results = self.http.get_request("iss")

                self.temp_validator = ResponseValidator(temp_results, self.data)
                print(
                    f"There are {len(self.temp_validator.results)}"
                    + f" issues in the matching volume: '{k}'."
                )
                temp_results = self.temp_validator.year_checker()
                self.temp_validator.results = temp_results
                temp_results = self.temp_validator.title_checker()
                self.temp_validator.results = temp_results

                print(
                    "After filtering for title and year "
                    + f"there are {len(temp_results)} results remaining."
                )
                if len(temp_results) != 0:
                    if len(temp_results) > 25:
                        print(
                            "Too many issues to compare covers, "
                            + f"skipping volume '{k}'."
                        )
                        skipped_vols.append((j, k, len(temp_results)))
                        continue
                    potential_results.extend(temp_results)
                    self.temp_validator.cover_img_url_getter(temp_results)
                    images = []
                    with ThreadPoolExecutor(max_workers=5) as executor:
                        images = list(
                            executor.map(
                                self.http.download_img, self.temp_validator.urls
                            )
                        )
                    matches_indices = []
                    for index, i in enumerate(images):
                        if i is None:
                            continue
                        try:
                            img_pil = Image.open(i)
                            score = self.temp_validator.cover_img_comp_w_weight(
                                self.coverhashes, img_pil
                            )
                            print(f"Index {index}: similarity score = {score:.2f}")
                            if score > 0.85:
                                matches_indices.append(index)
                        except Exception as e:
                            print(f"Error comparing image at index {index}: {e}.")
                    final_results = [temp_results[i] for i in matches_indices]
                    good_matches.extend(final_results)
                else:
                    continue

            if len(good_matches) == 1:
                print(good_matches[0]["volume"]["name"])
                print("There is ONE match!!!")
                print(good_matches)
                self.results.append(good_matches)
                return MatchCode.ONE_MATCH
            elif len(good_matches) == 0:
                print("There are no matches.")
                # If there is no matches need to do something.
                # Perhaps the comic is new and hasnt
                # been uploaded onto comicvine.
            elif len(good_matches) > 1:
                for i in good_matches:
                    print(i["volume"]["name"])
                self.results.extend(good_matches)
                # Need to use scoring or sorting or closest title match etc.
                # If that cant decide then we need to flag the comic
                # and ask the user for input.
        if len(self.results) == 0:
            print("There are no matches")
            return MatchCode.NO_MATCH, potential_results
            filterer = ResultsFilter(potential_results, self.data, self.path)
            self.filtered_for_none = filterer.present_choices()
            return MatchCode.NO_MATCH
        elif len(self.results) > 1:
            print("There are multiple matches")
            return MatchCode.MULTIPLE_MATCHES, self.results
            filterer = ResultsFilter(self.results, self.data, self.path)
            self.filtered_for_many = filterer.present_choices()
            return MatchCode.MULTIPLE_MATCHES


def run_tagging_process(filepath: Path, api_key: str) -> Optional[tuple[list, RequestData]]:
    """
    Drive the tagging workflow for a CBZ file: parse filename metadata, search for matching issue data, and insert metadata into the archive when a single match is found.
    
    Parameters:
        filepath (Path): Path to the CBZ file to be processed.
        api_key (str): API key used for remote metadata lookup.
    
    Returns:
        None if a single match is confirmed and metadata has been inserted into the CBZ; otherwise a tuple `(potential_matches, request_data)` where `potential_matches` is a list of candidate match dictionaries and `request_data` is the parsed RequestData built from the filename.
    """
    filename = filepath.stem
    lexer_instance = Lexer(filename)
    state: Optional[LexerFunc] = run_lexer
    while state is not None:
        state = state(lexer_instance)
    parser_instance = Parser(lexer_instance.items)
    comic_info = parser_instance.construct_metadata()
    print(comic_info)
    series = comic_info["series"]
    num = comic_info.get("issue", 0) or comic_info.get("volume", 0)
    year = comic_info.get("year", 0)
    title = comic_info.get("title")

    data = RequestData(int(num), int(year), str(series), str(title))

    tagger = TaggingPipeline(data=data, path=filepath, size=100, api_key=api_key)

    final_result = tagger.run()
    if final_result == MatchCode.ONE_MATCH:

        inserter = TagApplication(tagger.results[0], api_key, filename, session)
        inserter.get_request()
        inserter.create_metadata_dict()
        inserter.insert_xml_into_cbz(filepath)
        return None
    elif final_result[0] == MatchCode.NO_MATCH:
        return (final_result[1], tagger.data)
        print("Need another method to find matches")
        best_matches = tagger.filtered_for_none
        return (best_matches, tagger.data)
        # Add a method to rank and return the best 3-5 matches.
    elif final_result[0] == MatchCode.MULTIPLE_MATCHES:
        return (final_result[1], tagger.data)
        print("Multiple matches, require user input to disambiguate.")
        best_matches = tagger.filtered_for_many
        return (best_matches, tagger.data)
        # Need to create a gui popup to allow user to select correct match.
    else:
        raise ValueError("Something has gone wrong")


def extract_and_insert(match, api_key, filename: str, filepath: Path):
    inserter = TagApplication(match, api_key, filename)
    inserter.get_request()
    inserter.create_metadata_dict()
    inserter.insert_xml_into_cbz(filepath)
    return None
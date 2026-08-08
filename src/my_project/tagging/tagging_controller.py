import logging
import zipfile
from concurrent.futures import ThreadPoolExecutor
from enum import IntEnum
from io import BytesIO
from pathlib import Path

import cv2
import imagehash
import numpy as np
import requests
from imagehash import ImageHash
from PIL import Image

from my_project.classes.helper_classes import (
    ComicVineIssueStruct,
    ComicVineSearchStruct,
    Publisher,
)
from my_project.tagging.lexer import Lexer
from my_project.tagging.parser import Parser
from my_project.tagging.requester import HttpRequest, RequestData
from my_project.tagging.validator import IssueResponseValidator, SearchResponseValidator

logger = logging.getLogger(__name__)

HASH_SIZE = 16


class MatchCode(IntEnum):
    NO_MATCH = 0
    ONE_MATCH = 1
    MULTIPLE_MATCHES = 2


header = {
    "User-Agent": "AutoComicLibrary/1.0 (contact: adam.perrott@protonmail.com;"
    "github.com/CloakedLeader/comic_library)",
    "Accept": r"*/*",
    "Referer": "https://comicvine.gamespot.com/",
    # "Accept-Encoding": "gzip,deflate,br",
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
        self.cover_colour_hist = self.create_cover_hist()
        self.results: list[ComicVineIssueStruct] = []

    def cover_getter(self):
        with zipfile.ZipFile(str(self.path), "r") as zip_ref:
            image_files = [
                f
                for f in zip_ref.namelist()
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if not image_files:
                logger.info(f"Empty archive in {self.path}")
                raise ValueError("Empty archive.")

            image_files.sort()
            cover = zip_ref.read(image_files[0])
            return BytesIO(cover)

    def cover_hasher(self) -> dict[str, ImageHash]:
        image = Image.open(self.cover)
        return {
            "phash": imagehash.phash(image, hash_size=HASH_SIZE),
            "dhash": imagehash.dhash(image, hash_size=HASH_SIZE),
            "ahash": imagehash.average_hash(image, hash_size=HASH_SIZE),
        }

    def create_cover_hist(self):
        with Image.open(self.cover) as pil_img:
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist(
            [hsv], [0, 1, 2], None, [16, 8, 8], [0, 180, 0, 256, 0, 256]
        )
        return cv2.normalize(hist, None, alpha=1.0, norm_type=cv2.NORM_L1)  # type: ignore

    def compare_images(self, images: list[BytesIO]) -> list[int]:
        weights = {"phash": 0.7, "dhash": 0.2, "ahash": 0.1}
        results: list[tuple[int, float, float, float]] = []
        for index, i in enumerate(images):
            with Image.open(i) as unsure_img:
                img = cv2.cvtColor(np.array(unsure_img), cv2.COLOR_RGB2BGR)
                unsure_hashes = {
                    "phash": imagehash.phash(unsure_img, hash_size=HASH_SIZE),
                    "dhash": imagehash.dhash(unsure_img, hash_size=HASH_SIZE),
                    "ahash": imagehash.average_hash(unsure_img, hash_size=HASH_SIZE),
                }
            hash_score = sum(
                weights[k] * (1 - (self.coverhashes[k] - unsure_hashes[k]) / 256)
                for k in weights
            )

            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist(
                [hsv], [0, 1, 2], None, [16, 8, 8], [0, 180, 0, 256, 0, 256]
            )
            hist = cv2.normalize(hist, None, alpha=1.0, norm_type=cv2.NORM_L1)  # type: ignore
            bhatt = cv2.compareHist(
                self.cover_colour_hist, hist, cv2.HISTCMP_BHATTACHARYYA
            )
            hist_score = 1.0 - bhatt

            total = 0.2 * hash_score + 0.8 * hist_score
            results.append((index, hash_score, hist_score, total))
            logger.info(
                f"idx={index} hash={hash_score:.3f} hist={hist_score:.3f} total={total:.3f}"
            )

        sorted_scores = sorted(results, key=lambda x: x[3], reverse=True)
        if len(sorted_scores) == 1:
            if sorted_scores[0][3] > 0.75:
                return [sorted_scores[0][0]]
            else:
                return []
        margin = sorted_scores[0][1] - sorted_scores[1][1]
        ratio = sorted_scores[0][1] / max(sorted_scores[1][1], 1e-9)
        if margin > 0.3 or ratio > 2.0:
            return [sorted_scores[0][0]]
        else:
            return [k[0] for k in sorted_scores if k[3] > 0.75]

    def run(self) -> MatchCode:
        queries: set[str] = set(
            [
                f"{self.data.series} {self.data.title or ''}".strip(),
                self.data.series,
                self.data.title,
            ]
        )
        self.potential_results: list = []

        skipped_vols = []
        possible_ids: list[int] = []
        self.search_results: list[ComicVineSearchStruct] = []
        for q in queries:
            if q == "":
                continue
            logger.info(f"Query: {q}")
            self.http.build_url_search(q)
            results = self.http.search_get_request()
            self.search_validator = SearchResponseValidator(results.results, self.data)

            logger.info(f"There are {len(results.results)} results returned.")
            filtered_results = self.search_validator.filter_search_results()
            for filtered in filtered_results:
                logger.info(filtered)
            logger.info(
                "After filtering for title, publisher and issue "
                + f"there are {len(filtered_results)} remaining results."
            )

            if len(filtered_results) == 0:
                continue

            self.search_results.extend(filtered_results)

            vol_info = [(i.id, i.name) for i in filtered_results]
            final_results: list[ComicVineIssueStruct] = []
            for j, k in vol_info:
                self.http.build_url_iss(j)
                issue_results = self.http.issue_get_request()

                self.issue_validator = IssueResponseValidator(
                    issue_results.results, self.data
                )
                logger.info(
                    f"There are {len(self.issue_validator.results)}"
                    + f" issues in the matching volume: '{k}' for query {q}."
                )
                temp_results = self.issue_validator.filter_issue_results()

                logger.info(
                    "After filtering for title and year "
                    + f"there are {len(temp_results)} results remaining for query {q}"
                )

                if len(temp_results) == 0:
                    continue

                if len(temp_results) > 20:
                    logger.info(
                        "Too many issues to compare covers, "
                        + f"skipping volume '{k}'."
                    )
                    skipped_vols.append((j, k, len(temp_results)))
                    continue

                self.potential_results.extend(temp_results)
                for result in temp_results:
                    if result.id not in possible_ids:
                        final_results.append(result)

            if len(final_results) == 1:
                image = self.http.download_img(final_results[0].image.medium_url)
                if self.compare_images([image]):
                    logger.info(f"There is ONE match for query: {q}")
                    logger.info(f"The match is: {final_results[0].volume.name}")
                    self.results.extend(final_results)
                    possible_ids.append(final_results[0].id)
                    break
                else:
                    continue

            elif len(final_results) == 0:
                logger.warning(f"There are no matches for query {q}.")
                continue

            elif len(final_results) > 1:
                images: list[BytesIO] = []
                with ThreadPoolExecutor(max_workers=5) as executor:
                    images = list(
                        executor.map(
                            self.http.download_img,
                            [struct.image.medium_url for struct in final_results],
                        )
                    )
                image_match_indices = self.compare_images(images)
                self.results.extend([final_results[pos] for pos in image_match_indices])
                possible_ids.extend([res.id for res in final_results])
                continue
                # Need to use scoring or sorting or closest title match etc.
                # If that cant decide then we need to flag the comic
                # and ask the user for input.
        if len(self.results) == 1:
            logger.info("There is ONE MATCH!!!")
            return MatchCode.ONE_MATCH
        elif len(self.results) == 0:
            logger.warning("There are no matches")
            return MatchCode.NO_MATCH
        elif len(self.results) > 1:
            # ! Need to implement a greater detail image matcher, perhaps ORB or SIFT
            logger.warning(f"There are multiple matches ({len(self.results)})")
            logger.info(f"The matches are: {", ".join([g.name for g in self.results])}")  # type: ignore
            return MatchCode.MULTIPLE_MATCHES
        else:
            return MatchCode.NO_MATCH

    def get_publisher_info(self, volume_id: int) -> Publisher:
        for i in self.search_results:
            if i.id == volume_id:
                return i.publisher if i.publisher else Publisher(name="Empty")
        return Publisher(name="Empty")


def run_tagging_process(
    filepath: Path, api_key: str
) -> tuple[TaggingPipeline, MatchCode]:
    filename = filepath.stem

    lexer_instance = Lexer(filename)
    logger.info("Starting lexing the filename.")
    lexer_instance.run()
    logger.info(lexer_instance.format_items())

    parser_instance = Parser(lexer_instance.items)
    logger.info("Starting parsing lexed items.")
    comic_info = parser_instance.parse()
    logger.info(f"The filename {filename} gives the following info:\n {comic_info}")

    series = comic_info.series
    num = comic_info.volume_number
    year = comic_info.year
    title = comic_info.title

    data = RequestData(num, year, series, title)

    tagger = TaggingPipeline(
        data=data, path=filepath, size=filepath.stat().st_size, api_key=api_key
    )

    return (tagger, tagger.run())

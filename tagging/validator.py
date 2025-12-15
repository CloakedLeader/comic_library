import re
from difflib import SequenceMatcher
from typing import Callable

import imagehash
from PIL import Image
from rapidfuzz import fuzz

from classes.helper_classes import APIResults

from .requester import RequestData


class ResponseValidator:
    issue_threshold = 70
    volume_threshold = 50

    def __init__(self, response: APIResults, expected_data: RequestData) -> None:
        """
        Initialise the validator with API response results and the expected
        request data.

        Args:
            response (dict): API response containing a "results" key whose
                value is a list of result dictionaries.
            expected_data (RequestData): Expected metadata for the request
                to return.
        """

        self.results = response.results
        self.expected_info = expected_data

    def filter_results(self, predicate: Callable) -> list:
        """
        Filter stored results using some predicate.

        Args:
            predicate (Callable): A function that recieves a single result
                item and returns a truthy value to include that item.

        Returns:
            list: The subset of 'self.results' which fulfills the predicate.
        """

        return [item for item in self.results if predicate(item)]

    def year_checker(self) -> list:
        """
        Filter results to those whose year is within 4 years of the expected
        publication year.

        Returns:
            list: Result items for which the year is within 4 of the expected
                year of publication.
        """

        def check_year(item):
            year = int(item["date_added"][:4])
            return abs(year - self.expected_info.pub_year) <= 4

        return self.filter_results(check_year)

    @staticmethod
    def fuzzy_match(a: str, b: str, threshold: int = 65) -> bool:
        """
        Determine similarity of two strings using token-sort fuzzy matching.

        Args:
            a (str): First string to compare.
            b (str): Second string to compare.
            threshold (int, optional): Minimum similarity percentage to consider
                strings a match. Defaults to 65.

        Returns:
            bool: True if the strings similarity is greater or equal to 'threshold'.
                False otherwise.
        """

        return fuzz.token_sort_ratio(a, b) >= threshold

    def pick_best_volumes(self, number: int = 5) -> list:
        """
        Selects the top matching volume results whose names best match the expected
        series name.

        Args:
            number (int, optional): Maximum number of top-matching results to return.
                Defaults to 5.

        Returns:
            list: The selected result dictionaries ordered from highest to lowest via
                the name-match score.
        """

        def score_name(item):
            score = 0.0
            name = item["name"]
            if name:
                score += SequenceMatcher(
                    None, name.lower(), self.expected_info.series.lower()
                ).ratio()
            return score

        scored_volumes = [(i, score_name(item)) for i, item in enumerate(self.results)]
        scored_volumes.sort(key=lambda x: x[1], reverse=True)
        top_indices = [i for i, _ in scored_volumes[:number]]
        return [self.results[i] for i in top_indices]

    def title_checker(self) -> list:
        """
        Filter stored results by comparing each item's title to the expected
        title using fuzzy matching.

        Ambiguous titles include short forms like "tpb" or "hc" and patterns such as
        volume markers like "vol 1" or "book one". When the title is ambiguous, the
        volume title is used instead.

        Returns:
            list: The subset of  self.results  whose title matches accoring to the
                configured fuzzy-match threshold.
        """

        def check_title(item):
            used_fallback = False
            ambig_names = ["tpb", "hc", "omnibus"]
            ambig_regexes = [
                r"^vol(?:ume)?\.?\s*\d+$",  # matches "vol.", "volume", "vol"
                r"^#\d+$",  # matches "#1", "#12" etc
                r"^issue\s*\d+$",  # matches "issue 3"
                r"\bvol(?:ume)?\.?\s*(one|two|three|four|\d+|i{1,3}|iv|v)\b",
                r"\bbook\s*(one|two|three|four|\d+|i{1,3}|iv|v)\b",
            ]
            title = item["name"]
            if title:
                lowered_title = title.lower().strip()
                is_ambig = lowered_title in ambig_names or any(
                    re.match(p, lowered_title) for p in ambig_regexes
                )
                if is_ambig:
                    title = item.get("volume", {}).get("name")
                    used_fallback = True
            else:
                title = item.get("volume", {}).get("name")
                used_fallback = True
            if title is None:
                return False
            threshold = (
                ResponseValidator.volume_threshold
                if used_fallback
                else ResponseValidator.issue_threshold
            )
            return self.fuzzy_match(
                title, self.expected_info.unclean_title, threshold=threshold
            )

        return self.filter_results(check_title)

    def pub_checker(self, results: list) -> list:
        """
        Filter a list of results by publisher credibility.

        Filters out results which are published by foreign publishers.
        Specifically looks for common english-language publisher keywords.

        Args:
            results (list): A list of results that include a "publisher" dictionary.

        Returns:
            list: The filtered list of result dictionaries that passed the publisher
                checks.
        """

        foriegn_keywords = {
            "panini",
            "verlag",
            "norma",
            "televisa",
            "planeta",
            "deagostini",
            "urban",
        }
        english_publishers = {
            "Marvel": 31,
            "DC Comics": 10,
            "Image": 513,
            "IDW Publishing": 1190,
            "Dark Horse Comics": 364,
        }

        filtered = []
        for result in results:
            pub_dict = result["publisher"]
            pub_id = pub_dict["id"]
            pub_name = pub_dict["name"]
            if pub_id in english_publishers.values():
                filtered.append(result)
            elif any(word.lower() in foriegn_keywords for word in pub_name.split()):
                print(f"Filtered out {pub_name} due to foreign publisher.")
            else:
                filtered.append(result)
                print(f"Accepted '{pub_name}' but please check.")
        return filtered

    def issue_count_filter(self, limit: int = 12) -> list:
        """
        Filter results to exclude items that have too many issues.

        Args:
            limit (int, optional): Maximum number of issues to be considered a series
                of collected editions. Defaults to 12.

        Returns:
            list: A list of result items from self.results whose count is less than 12.
        """

        def is_collection(item):
            issue_count = item["count_of_issues"]
            return True if issue_count < limit else False

        return self.filter_results(is_collection)

    def cover_img_url_getter(self, filtered_results: list) -> None:
        """
        Collects thumbnail image URL's from a list of result items and stores
        them on the instance.

        Args:
            filtered_results (list): List of result dictionaries that contain a
                sub-dictionary "image". Populates self.urls as a list of these
                thumbnail URL strings.
        """

        self.urls = []
        for i in filtered_results:
            self.urls.append(i["image"]["thumb_url"])

    def cover_img_comparison(
        self, known_image_hash, unsure_image_bytes, threshold=8
    ) -> bool:
        """
        Compare an unknown image to a known image hash using a perceptual
        hash distance threshold.

        Args:
            known_image_hash (_type_): An imagehash.ImageHash representing
                the known image's perceptual hash.
            unsure_image_bytes (_type_): A file-like object or bytes for the image
                to compare.
            threshold (int, optional): Maximum allowed hash distance for images
                to be considered a match. Defaults to 8.

        Returns:
            bool: True if the perceptual hash distance is less or equal to the threshold.
                False otherwise.
        """

        unsure_image = Image.open(unsure_image_bytes)
        hash1 = known_image_hash
        hash2 = imagehash.phash(unsure_image)
        hash_diff = hash1 - hash2
        print(
            f"[DEBUG] Hashing distance = \
              {hash_diff}, threshold = {threshold}"
        )
        return hash_diff <= threshold

    def cover_img_comp_w_weight(
        self, known_image_hashes, unsure_image_bytes, max_dist=64
    ) -> float:
        """
        Compute a weighted similarity score between a known image and a
        possible match.

        Args:
            known_image_hashes (_type_): Different hash values for the known
                image.
            unsure_image_bytes (_type_): An image-like object accepted by
                by imagehash. Used to compute p, d and a hashes.
            max_dist (int, optional): Maximum distance used to normalise
                individual hash distances. Defaults to 64.

        Returns:
            float: Weighted similarity where higher values represent greater
                similarity.
        """

        weights = {"phash": 0.6, "dhash": 0.2, "ahash": 0.2}
        with Image.open(unsure_image_bytes) as img:
            unsure_hashes = {
                "phash": imagehash.phash(img),
                "dhash": imagehash.dhash(img),
                "ahash": imagehash.average_hash(img),
            }
        score = 0.0
        for key in weights:
            dist = known_image_hashes[key] - unsure_hashes[key]
            normalised = 1 - (dist / max_dist)
            score += weights[key] * normalised
        return score

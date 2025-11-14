import re
from difflib import SequenceMatcher
import imagehash
from fuzzywuzzy import fuzz
from PIL import Image

from requester import RequestData


class ResponseValidator:

    issue_threshold = 70
    volume_threshold = 50

    def __init__(self, response: dict, expected_data: RequestData):
        """
        Initialise the validator with API response results and the expected request data.
        
        Parameters:
            response (dict): API response containing a "results" key whose value is a list of result dictionaries; this list is stored on the instance as `self.results`.
            expected_data (RequestData): Expected metadata for the request (publication title, year, etc.) stored on the instance as `self.expected_info`.
        """
        self.results = response["results"]
        self.expected_info = expected_data

    def filter_results(self, predicate):
        """
        Filter stored results using a predicate.
        
        Parameters:
            predicate (callable): A function that receives a single result item and returns a truthy value to include that item.
        
        Returns:
            list: The subset of `self.results` for which `predicate(item)` is truthy.
        """
        return [item for item in self.results if predicate(item)]

    def year_checker(self):
        """
        Filter results to those whose recorded year is within four years of the expected publication year.
        
        Returns:
            list: Result items for which the year extracted from item["date_added"] (first four characters) is within 4 years of self.expected_info.pub_year.
        """
        def check_year(item):
            year = int(item["date_added"][:4])
            return abs(year - self.expected_info.pub_year) <= 4

        return self.filter_results(check_year)

    @staticmethod
    def fuzzy_match(a, b, threshold=65):
        """
        Determine similarity of two strings using token-sort fuzzy matching.
        
        Parameters:
            a (str): First string to compare.
            b (str): Second string to compare.
            threshold (int): Minimum similarity percentage (0–100) required to consider the strings a match.
        
        Returns:
            `true` if the strings' similarity is greater than or equal to `threshold`, `false` otherwise.
        """
        return fuzz.token_sort_ratio(a, b) >= threshold

    def pick_best_volumes(self, number: int = 5):
        """
        Selects the top matching volume results whose names best match the expected series name.
        
        Parameters:
            number (int): Maximum number of top-matching results to return.
        
        Returns:
            list: The selected result dictionaries ordered from highest to lowest name-match score.
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

    def title_checker(self):
        """
        Filter stored results by comparing each item's title (or a fallback volume name for ambiguous/missing titles) to the expected unclean title using fuzzy matching.
        
        Ambiguous titles include short forms like "tpb", "hc", "omnibus" and patterns such as volume/issue markers (e.g. "vol 1", "#1", "issue 3", "book one"); when an item's title is ambiguous or missing, the item's volume.name is used as a fallback. The fuzzy-match threshold is ResponseValidator.volume_threshold when a fallback is used, otherwise ResponseValidator.issue_threshold.
        
        Returns:
            list: The subset of self.results whose (possibly fallback) title matches self.expected_info.unclean_title according to the configured fuzzy-match threshold.
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

    def pub_checker(self, results: list):
        """
        Filter a list of result records by publisher credibility.
        
        Filters in results whose publisher id is in a predefined set of recognised English publishers, excludes results whose publisher name contains any predefined foreign-language keyword, and accepts all other results. This function may print diagnostic messages when it excludes or tentatively accepts a publisher.
        
        Parameters:
            results (list): Iterable of result dictionaries; each must contain a "publisher" dict with "id" and "name" keys.
        
        Returns:
            list: The filtered list of result dictionaries that passed publisher checks.
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

    def issue_count_filter(self, limit: int = 12):
        """
        Filter results to exclude items that have too many issues.
        
        Parameters:
            limit (int): Maximum number of issues allowed for an item to be considered a single run/series. Items with
                `count_of_issues` strictly less than this value are kept. Defaults to 12.
        
        Returns:
            list: A list of result items from `self.results` whose `count_of_issues` is less than `limit`.
        """
        def is_collection(item):
            issue_count = item["count_of_issues"]
            return True if issue_count < limit else False

        return self.filter_results(is_collection)

    def cover_img_url_getter(self, filtered_results):
        """
        Collects thumbnail image URLs from a list of result items and stores them on the instance.
        
        Parameters:
            filtered_results (list): Iterable of result dictionaries where each item contains an "image" mapping with a "thumb_url" key. Populates self.urls as a list of these thumbnail URL strings.
        """
        self.urls = []
        for i in filtered_results:
            self.urls.append(i["image"]["thumb_url"])

    def cover_img_comparison(
        self, known_image_hash, unsure_image_bytes, threshold=8
    ) -> bool:  # Returns true if it finds match.
        """
        Compare an unknown image to a known image hash using a perceptual hash distance threshold.
        
        Parameters:
            known_image_hash: An imagehash.ImageHash representing the known image's perceptual hash.
            unsure_image_bytes: A file-like object or bytes for the image to compare.
            threshold (int): Maximum allowed hash distance for images to be considered a match.
        
        Returns:
            bool: `true` if the perceptual hash distance between the known hash and the unsure image is less than or equal to `threshold`, `false` otherwise.
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
    ):
        """
        Compute a weighted similarity score between a known set of image hashes and an image.
        
        Parameters:
            known_image_hashes (dict): Mapping with keys 'phash', 'dhash' and 'ahash' to imagehash objects representing the reference image.
            unsure_image_bytes: An image-like object accepted by imagehash (e.g. PIL Image); used to compute phash, dhash and average hash for the candidate image.
            max_dist (int): Maximum distance used to normalise individual hash distances (higher values make distances contribute less); defaults to 64.
        
        Returns:
            float: Weighted similarity score where higher values indicate greater similarity (values close to 1 mean very similar by the provided hashes).
        """
        weights = {"phash": 0.6, "dhash": 0.2, "ahash": 0.2}
        unsure_hashes = {
            "phash": imagehash.phash(unsure_image_bytes),
            "dhash": imagehash.dhash(unsure_image_bytes),
            "ahash": imagehash.average_hash(unsure_image_bytes),
        }
        score = 0.0
        for key in weights:
            dist = known_image_hashes[key] - unsure_hashes[key]
            normalised = 1 - (dist / max_dist)
            score += weights[key] * normalised
        return score
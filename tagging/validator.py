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
        self.results = response["results"]
        self.expected_info = expected_data

    def filter_results(self, predicate):
        return [item for item in self.results if predicate(item)]

    def year_checker(self):
        def check_year(item):
            year = int(item["date_added"][:4])
            return abs(year - self.expected_info.pub_year) <= 4

        return self.filter_results(check_year)

    @staticmethod
    def fuzzy_match(a, b, threshold=65):
        return fuzz.token_sort_ratio(a, b) >= threshold

    def pick_best_volumes(self, number: int = 5):
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
        def is_collection(item):
            issue_count = item["count_of_issues"]
            return True if issue_count < limit else False

        return self.filter_results(is_collection)

    def cover_img_url_getter(self, filtered_results):
        self.urls = []
        for i in filtered_results:
            self.urls.append(i["image"]["thumb_url"])

    def cover_img_comparison(
        self, known_image_hash, unsure_image_bytes, threshold=8
    ) -> bool:  # Returns true if it finds match.
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
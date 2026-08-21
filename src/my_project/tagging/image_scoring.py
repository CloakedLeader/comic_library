import logging
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import cv2
import imagehash
import numpy as np
from PIL import Image

from my_project.classes.tagging_classes import Candidate
from my_project.tagging.requester import HttpRequest

logger = logging.getLogger(__name__)


class ImageScorer:
    HASH_SIZE = 16
    WEIGHTS = {"phash": 0.7, "dhash": 0.2, "ahash": 0.1}
    FINAL_WEIGHTS = {"hash": 0.6, "hue_hist": 0.4}

    def __init__(self, actual_cover: BytesIO, http: HttpRequest):
        self.cover = Image.open(actual_cover).convert("RGB")
        self.padded_cover = self.pad_to_square(self.cover)
        self.actual_hashes = {
            "phash": imagehash.phash(
                self.padded_cover, hash_size=ImageScorer.HASH_SIZE
            ),
            "dhash": imagehash.dhash(
                self.padded_cover, hash_size=ImageScorer.HASH_SIZE
            ),
            "ahash": imagehash.average_hash(
                self.padded_cover, hash_size=ImageScorer.HASH_SIZE
            ),
        }
        actual_cv2 = cv2.cvtColor(np.array(self.cover), cv2.COLOR_RGB2BGR)
        self.histogram = (
            self.saturation_weighted_hue_hist(actual_cv2).flatten().astype(np.float64)
        )
        self.http = http

    @staticmethod
    def pad_to_square(img: Image.Image, fill=(0, 0, 0)) -> Image.Image:
        w, h = img.size
        size = max(w, h)
        canvas = Image.new("RGB", (size, size), fill)
        canvas.paste(img, ((size - w) // 2, (size - h) // 2))
        return canvas

    @staticmethod
    def saturation_weighted_hue_hist(
        img_cv: np.ndarray, bins: int = 30, sat_floor: float = 0.15
    ) -> np.ndarray:
        hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV).astype(np.float64)
        h = hsv[:, :, 0].flatten()
        s = (hsv[:, :, 1] / 255.0).flatten()

        mask = s >= sat_floor
        h, s = h[mask], s[mask]

        if h.size == 0:
            return np.zeros(bins, dtype=np.float64)

        hist, _ = np.histogram(h, bins=bins, range=(0, 180), weights=s)
        total = hist.sum()
        if total > 0:
            hist = hist / total
        return hist

    def measure_correlation(
        self, possible_hist: np.ndarray, eps: float = 1e-10
    ) -> float:
        h2 = possible_hist.flatten().astype(np.float64)
        h1_centered = self.histogram - self.histogram.mean()
        h2_centered = h2 - h2.mean()
        numerator = np.sum(h1_centered * h2_centered)
        denominator = np.sqrt(np.sum(h1_centered**2) * np.sum(h2_centered**2)) + eps
        corr = numerator / denominator
        return float(np.clip(corr, -1.0, 1.0))

    def score_image(self, possible_image: BytesIO):
        image = Image.open(possible_image).convert("RGB")
        padded_image = self.pad_to_square(image)
        possible_hashes = {
            "phash": imagehash.phash(padded_image, hash_size=ImageScorer.HASH_SIZE),
            "dhash": imagehash.dhash(padded_image, hash_size=ImageScorer.HASH_SIZE),
            "ahash": imagehash.average_hash(
                padded_image, hash_size=ImageScorer.HASH_SIZE
            ),
        }
        possible_cv2 = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        possible_hist = self.saturation_weighted_hue_hist(possible_cv2)
        corr = self.measure_correlation(possible_hist)

        hist_score = (corr + 1) / 2
        hash_score = sum(
            ImageScorer.WEIGHTS[k]
            * (
                1
                - (self.actual_hashes[k] - possible_hashes[k])
                / (ImageScorer.HASH_SIZE**2)
            )
            for k in ImageScorer.WEIGHTS
        )

        actual_aspect = self.cover.size[0] / self.cover.size[1]
        possible_aspect = image.size[0] / image.size[1]
        aspect_diff = abs(actual_aspect - possible_aspect) / max(
            actual_aspect, possible_aspect
        )
        if aspect_diff >= 0.03:
            w_hash, w_hue = 0.3, 0.7
        else:
            w_hash, w_hue = (
                ImageScorer.FINAL_WEIGHTS["hash"],
                ImageScorer.FINAL_WEIGHTS["hue_hist"],
            )

        final_score = w_hash * hash_score + w_hue * hist_score
        logger.info(f"""   hash-score = {hash_score}
                            histogram-score = {hist_score}
                            total-score = {final_score}
                            """)
        # return {
        #     "hash_score": hash_score,
        #     "hist_score": hist_score,
        #     "aspect_diff": aspect_diff,
        #     "weights_used": (w_hash, w_hue),
        #     "total": final_score,
        # }
        return final_score

    def score_candidate_images(self, possibles: list[Candidate]) -> list[Candidate]:
        scored_candidates = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(self.http.download_img, entry.issue.image.medium_url)
                for entry in possibles
            ]

        for entry, future in zip(possibles, futures, strict=False):
            logger.info("Started processing the cover %s.", entry.issue.volume.name)
            try:
                entry.image_score = self.score_image(future.result())
            except Exception:
                logger.exception(
                    "Failed to load the cover of %s.", entry.issue.volume.name
                )
                continue
            scored_candidates.append(entry)

        return scored_candidates

import random
import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional

import Levenshtein
from PIL import Image


class ImageExtraction:
    def __init__(self, path: Path, output_dir: Path, primary_key: str) -> None:
        self.filepath = path
        self.output_folder = output_dir
        self.primary_key = primary_key
        self.image_names: list[str] = self.get_namelist()
        self.cover_bytes: Optional[bytes] = None

    @staticmethod
    def score(name: str) -> tuple[int, int, str]:
        COVER_CUES = re.compile(r"\b(?:cover|front|fc)\b", re.IGNORECASE)
        NUMBERS = re.compile(r"\d+")
        stem = Path(name)
        lowered = str(stem).lower()

        if COVER_CUES.search(lowered) or lowered.endswith("00"):
            return (0, 0, name)

        numbers = [int(n) for n in NUMBERS.findall(str(stem))]
        for num in numbers:
            if num in (0, 1):
                return (1, num, name)

        if numbers:
            return (2 + min(numbers), min(numbers), name)

        return (10, 0, name)

    def get_namelist(self) -> list[str]:
        with zipfile.ZipFile(self.filepath, "r") as zip_ref:
            images = [
                f for f in zip_ref.namelist() if f.endswith((".jpg", ".jpeg", ".png"))
            ]
        return images

    def choose_cover(self) -> str:
        """
        Finds the cover image of a comic.

        Returns:
            The filepath of the image file believed to be the cover.
        """
        if not self.image_names:
            raise ValueError("Empty file list")

        ranked: list[tuple[int, int, str]] = sorted(
            self.score(f) for f in self.image_names
        )
        return ranked[0][-1]

    def extract_image_bytes(self) -> None:
        cover_file_name = self.choose_cover()
        with zipfile.ZipFile(self.filepath, "r") as zf:
            with zf.open(cover_file_name) as img_file:
                self.cover_bytes = img_file.read()

    def save_cover(self) -> tuple[Path, Path]:
        """
        Saves two copies of the same image with different sizes
        and suffixes to their filename.

        Returns:
            A tuple containing the file path of two images (smaller, bigger).
        """
        t_height = 400
        b_height = 800
        variants: dict[str, bytes] = {}
        if self.cover_bytes is None:
            raise ValueError("cover_bytes cannot be None")
        with Image.open(BytesIO(self.cover_bytes)) as img:
            for name, height in [("thumbnail", t_height), ("browser", b_height)]:
                w, h = img.size
                new_w = int(w * (height / h))
                resized_img = img.resize((new_w, height), Image.Resampling.LANCZOS)

                if name == "thumbnail":
                    quality = 90
                else:
                    quality = 80

                buffer = BytesIO()
                resized_img.save(buffer, format="JPEG", quality=quality, optimize=True)
                variants[name] = buffer.getvalue()

        file_dict: dict[str, tuple[bytes, Path]] = {}
        for key, value in variants.items():
            if key == "thumbnail":
                out_path_t = self.output_folder / f"{self.primary_key}_t.jpg"
                file_dict["thumbnail"] = (value, out_path_t)
            elif key == "browser":
                out_path_b = self.output_folder / f"{self.primary_key}_b.jpg"
                file_dict["browser"] = (value, out_path_b)

        for _, (data, path) in file_dict.items():
            with open(path, "wb") as f:
                f.write(data)

        return file_dict["thumbnail"][1], file_dict["browser"][1]

    def find_credit_pages(self) -> Optional[str]:
        """
        Searches for comic ripper pages among the image files.
        Identifies comic ripper pages by filenames that are very different
        from the names of the first 40% of files.

        Raises:
            ValueError: if there are no images found in the archive on filepath.

        Returns the filepath of the supposed credit page or None if
        nothing is found.
        """
        if not self.image_names:
            raise ValueError("Empty archhve: no image files found.")

        self.image_names.sort()
        common_files_index = int(len(self.image_names) * 0.4)
        early_files = self.image_names[:common_files_index]
        file_paths_to_compare = random.sample(early_files, min(5, len(early_files)))  # nosec B311
        last_files = self.image_names[-3:]
        not_matching_files = {
            j
            for j in last_files
            for k in file_paths_to_compare
            if Levenshtein.distance(j, k) > 10
        }

        if len(not_matching_files) == 1:
            return next(iter(not_matching_files))
        else:
            return None

    def run(self):
        try:
            self.extract_image_bytes()
            self.save_cover()
            print("[INFO] Cover saved!")
        except Exception as e:
            print(f"[ERROR] {e}")

import unittest
import zipfile
from pathlib import Path

from sort_function import choose_cover

ROOT_DIR = Path("D:\\comic_library\\comic_examples")

EXPECTED_COVERS = {
    "Booster Gold Vol. 1 #04 (May 1986)": "Booster Gold (1986-1988) 004-000.jpg",
    "Green Lantern Emerald Dawn #01 (December 1989)": "Green Lantern - Emerald Dawn (1989-1990) 001-000.jpg",
    "Runaways by Rowell TPB #02 (October 2018)": "Runaways by Rainbow Rowell & Kris Anka v02 - Best Friends Forever-000.jpg",
    "Wonder Woman Dead Earth TPB (December 2020)": "Wonder Woman - Dead Earth-000.jpg"
}

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def iter_archives(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in (".cbz", ".zip"))


def make_test_method(archive_path: Path):
    def test(self):
        with zipfile.ZipFile(archive_path) as z:
            images = [
                info.filename
                for info in z.infolist()
                if Path(info.filename).suffix.lower() in IMG_EXTS
            ]
            self.assertTrue(
                images,
                msg=f"No images found in {archive_path}",
            )

            chosen = choose_cover(images)

            self.assertIn(
                chosen,
                images,
                msg=f"{chosen} not found inside {archive_path}",
            )

            stem = archive_path.stem
            expected = EXPECTED_COVERS.get(stem)
            if expected is not None:
                self.assertEqual(
                    Path(chosen).name,
                    Path(expected).name,
                    msg=f"Cover mismatch for {archive_path}",
                )
    return test


class CoverTests(unittest.TestCase):
    """
    Dynamically populated.
    """


for cbz in iter_archives(ROOT_DIR):
    # Turn "Batman Year One.cbz" → "Batman_Year_One"
    slug = (
        cbz.relative_to(ROOT_DIR)
        .with_suffix("")
        .as_posix()
        .replace("/", "__")
        .replace(" ", "_")
    )
    test_name = f"test_{slug}"
    setattr(CoverTests, test_name, make_test_method(cbz))

if __name__ == "__main__":
    unittest.main(verbosity=2)

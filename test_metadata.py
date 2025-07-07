import unittest
import xml.etree.ElementTree as ET
import os
import zipfile
from metadata import get_text, find_metadata


class TestGetText(unittest.TestCase):
    def setUp(self):
        self.root = find_metadata(r"D:\comic_library\comic_examples\Juggernaut "
        "- No Stopping Now TPB (March 2021).cbz")

    def test_valid_tag(self):
        self.assertEqual(
            get_text(self.root, "Writer"),
            "fabian nicieza"
        )

    def test_missing_tag(self):
        xml = """<ComicInfo><Writer>Alan Moore</Writer>
        <EmptyTag></EmptyTag></ComicInfo>"""
        dummy_root = ET.fromstring(xml)
        with self.assertRaises(KeyError):
            get_text(dummy_root, "Penciller")

    def test_empty_tag(self):
        xml = """<ComicInfo><Writer>Alan Moore</Writer><EmptyTag></EmptyTag></ComicInfo>"""
        dummy_root = ET.fromstring(xml)
        with self.assertRaises(KeyError):
            get_text(dummy_root, "EmptyTag")


class TestFindMetadata(unittest.TestCase):
    def setUp(self):
        self.valid_cbz = r"D:\comic_library\comic_examples\Juggernaut" \
        " - No Stopping Now TPB (March 2021).cbz"
        self.invalid_cbz = r"D:\comic_library\comic_examples\bad.cbz"
        with open(self.invalid_cbz, "w") as f:
            f.write("not a zip file")

    def tearDown(self):
        os.remove(self.invalid_cbz)

    def test_valid_cbz(self):
        root = find_metadata(self.valid_cbz)
        self.assertEqual(root.tag, "ComicInfo")

    def test_invalid_zip(self):
        with self.assertRaises(zipfile.BadZipFile):
            find_metadata(self.invalid_cbz)

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            find_metadata("missing.cbz")

    def test_missing_comicinfo(self):
        path = "noinfo.cbz"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("NotComicInfo.xml", "<root></root>")
        with self.assertRaises(KeyError):
            find_metadata(path)
        os.remove(path)

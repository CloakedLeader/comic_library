import shutil
import tempfile
import unittest

from metadata import MetadataExtraction, MetadataProcessing

# class TestMetadataExtraction(unittest.TestCase):
#     @classmethod
#     def setUpClass(cls):
#         cls.path = "D:\\comic_library\\comic_examples\\Wonder Woman Dead Earth TPB (December 2020).cbz"
#         cls.tempdir = tempfile.mkdtemp()
#         print(f"Using temp dir: {cls.tempdir}")
#         cls.test_case = MetadataExtraction(cls.path, temp_dir=cls.tempdir)
#         assert cls.test_case.get_metadata()

#     @classmethod
#     def tearDownClass(cls):
#         shutil.rmtree(cls.tempdir)

#     def test_parse_comicinfo_xml_from_cbz(self):
#         self.assertEqual(self.test_case.has_complete_metadata(["Writer", "Publisher"]), True)

#     def test_easy_parsing1(self):
#         self.assertEqual(self.test_case.easy_parsing("Genre"), "Superhero")

#     def test_easy_parsing2(self):
#         self.assertEqual(self.test_case.easy_parsing("Year", int), 2020)

#     def test_parse_creators(self):
#         self.assertEqual(self.test_case.parse_creators(["Writer", "Colorist"]), [("Daniel Warren Johnson", "Writer"), ("Michael Spicer","Colorist")])

#     def test_parse_teams(self):
#         self.assertEqual(self.test_case.parse_characters_or_teams("Teams"), ["Amazons"])

#     def test_parse_characters(self):
#         self.assertEqual(self.test_case.parse_characters_or_teams("Characters"),
#                          ["Batman", "Cheetah (Minerva)", "Hippolyta", "Nubia", "Pegasus", "Steve Trevor", "Superman", "Wonder Woman"])


class TestTitleParsing(unittest.TestCase):
    def test_comictagger_quirk(self):
        raw = {
            "series": "Amazing Spider Man Modern Era Epic Collection: Coming Home",
            "title": "Volume 1",
        }
        comic = MetadataProcessing(raw)
        comic.title_parsing()

        self.assertEqual(comic.title_info["title"], "Coming Home")
        self.assertEqual(
            comic.title_info["series"], "Amazing Spider Man Modern Era Epic Collection"
        )
        self.assertEqual(comic.title_info["collection_type"], 4)
        self.assertEqual(comic.title_info["issue_num"], 1)

    def test_omnibus_keyword(self):
        raw = {"series": "X-Men Omnibus", "title": "Vol. 2"}
        comic = MetadataProcessing(raw)
        comic.title_parsing()
        self.assertEqual(comic.title_info["title"], "Vol. 2")
        self.assertEqual(comic.title_info["collection_type"], 2)
        self.assertEqual(comic.title_info["issue_num"], 2)

    def test_default_tpb(self):
        raw = {"series": "Saga", "title": "Volume 3"}
        comic = MetadataProcessing(raw)
        comic.title_parsing()

        self.assertEqual(comic.title_info["title"], "Volume 3")
        self.assertEqual(comic.title_info["collection_type"], 1)
        self.assertEqual(comic.title_info["issue_num"], 3)

    def test_title_vol_num(self):
        raw = {
            "series": "Ultimate X-Men by Peach Momoko",
            "title": "Vol. 2: Children of the Atom",
        }
        comic = MetadataProcessing(raw)
        comic.title_parsing()

        self.assertEqual(comic.title_info["title"], "Children of the Atom")
        self.assertEqual(comic.title_info["collection_type"], 1)
        self.assertEqual(comic.title_info["issue_num"], 2)
        self.assertEqual(comic.title_info["series"], "Ultimate X-men by Peach Momoko")

    def test_word_to_num(self):
        raw = {"series": "Action Comics", "title": "Vol. Four"}
        comic = MetadataProcessing(raw)
        comic.title_parsing()

        self.assertEqual(comic.title_info["issue_num"], 4)
        self.assertEqual(comic.title_info["title"], "Vol. Four")


if __name__ == "__main__":
    unittest.main()

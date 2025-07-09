import unittest
import shutil
import tempfile

from metadata import MetadataExtraction


class TestMetadataExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = "D:\\comic_library\\comic_examples\\Wonder Woman Dead Earth TPB (December 2020).cbz"
        cls.tempdir = tempfile.mkdtemp()
        print(f"Using temp dir: {cls.tempdir}")
        cls.test_case = MetadataExtraction(cls.path, temp_dir=cls.tempdir)
        assert cls.test_case.get_metadata()
   
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tempdir)

    def test_parse_comicinfo_xml_from_cbz(self):
        self.assertEqual(self.test_case.has_complete_metadata(["Writer", "Publisher"]), True)
   
    def test_easy_parsing1(self):
        self.assertEqual(self.test_case.easy_parsing("Genre"), "Superhero")

    def test_easy_parsing2(self):
        self.assertEqual(self.test_case.easy_parsing("Year", int), 2020)

    def test_parse_creators(self):
        self.assertEqual(self.test_case.parse_creators(["Writer", "Colorist"]), [("Daniel Warren Johnson", "Writer"), ("Michael Spicer","Colorist")])

    def test_parse_teams(self):
        self.assertEqual(self.test_case.parse_characters_or_teams("Teams"), ["Amazons"])
   
    def test_parse_characters(self):
        self.assertEqual(self.test_case.parse_characters_or_teams("Characters"),
                         ["Batman", "Cheetah (Minerva)", "Hippolyta", "Nubia", "Pegasus", "Steve Trevor", "Superman", "Wonder Woman"])
   

if __name__ == "__main__":
    unittest.main()

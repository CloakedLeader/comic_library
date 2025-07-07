import unittest
from dynamic_search import parse_search_query

class TestSearchParser(unittest.TestCase):
    def test_single_field(self):
        self.assertEqual(
            parse_search_query("char:wolverine"),
            'characters:"wolverine"'
        )

    def test_multiple_fields(self):
        self.assertEqual(
            parse_search_query("#mutant &marvel char:logan"),
            'tags:"mutant" AND publisher:"marvel" AND characters:"logan"'
        )

    def test_title_fallback(self):
        self.assertEqual(
            parse_search_query('x-men #mutant'),
            '"title:"x-men" AND tags:"mutant"'
        )
    
    def test_symbols_and_colons_mixed(self):
        self.assertEqual(
            parse_search_query("&dc cre:moore #watchmen"),
            'publisher:"dc" AND creators:"moore" AND tags:"watchmen'
        )

    def test_trailing_whitespace(self):
        self.assertEqual(
            parse_search_query('   #space    '),
            'tags:"space"'
        )

if name == "__main__":
    unittest.main()

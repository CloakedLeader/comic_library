from tagging.lexer import Lexer
from tagging.parser import Parser


def lex_and_parse(filename: str):
    lex = Lexer(filename)
    lex.run()
    parser = Parser(lex.items)
    comic_info = parser.parse()
    return comic_info


def test1():
    result = lex_and_parse("Batman Omnibus Vol 1 (2019)")

    assert result["collection_type"] == "Omnibus"
    assert result["year"] == 2019
    assert result["volume"] == 1


def test2():
    result = lex_and_parse("Batman v3 162 (2026) (Webrip) (The Last Kryptonian-DCP)")

    assert result["year"] == 2026
    assert result["issue"] == 162
    assert result["volume"] == 3
    assert result["series"] == "Batman"


def test3():
    result = lex_and_parse(
        "Spider-Boy - Full Circle v01 (2026) (digital) (Marika-Empire)"
    )

    assert result["title"] == "Full Circle"
    assert result["series"] == "Spider-Boy"
    assert result["year"] == 2026
    assert result["volume"] == 1


def test4():
    result = lex_and_parse(
        "Guardians of the Galaxy v01 - Cosmic Avengers (2013) (Digital) (F) (Zone-Empire)"
    )

    assert result["series"] == "Guardians of the Galaxy"
    assert result["title"] == "Cosmic Avengers"
    assert result["volume"] == 1
    assert result["year"] == 2013


def test5():
    result = lex_and_parse(
        "Justice League - The Atom Project (2025) (digital) (Son of Ultron-Empire)"
    )

    assert result["series"] == "Justice League"
    assert result["title"] == "The Atom Project"
    assert result["volume"] == 1 or 0
    assert result["year"] == 2025


def test6():
    result = lex_and_parse(
        "Moon Knight - Fist Of Khonshu - Subterranean Jungle v01 (2026) (digital) (Marika-Empire)"
    )

    assert result["series"] == "Moon Knight - Fist of Khonshu"
    assert result["title"] == "Subterranean Jungle"
    assert result["volume"] == 1
    assert result["year"] == 2026


def test7():
    result = lex_and_parse(
        "Doctor Strange Of Asgard v01 (2026) (digital) (Marika-Empire)"
    )

    assert result["series"] == "Doctor Strange of Asgard"
    assert result["volume"] == 1
    assert result["year"] == 2026

from tagging.lexer import Lexer
from tagging.parser import Parser


def lex_and_parse(filename: str):
    lex = Lexer(filename)
    lex.run()
    print("Lexing Completed")
    parser = Parser(lex.items)
    comic_info = parser.parse()
    print("Parsing Complete")
    return comic_info


def test_primitive():
    result = lex_and_parse("Batman No Man's Land (2015)")
    assert result["year"] == 2015
    assert result["title"] == "Batman No Man's Land".lower()


def test1():
    result = lex_and_parse("Batman Omnibus Vol 1 (2019)")

    assert result["collection"] == "omnibus"
    assert result["year"] == 2019
    assert result["volume"] == 1


def test2():
    result = lex_and_parse("Batman v3 162 (2026) (Webrip) (The Last Kryptonian-DCP)")

    assert result["year"] == 2026
    assert result["issue"] == 162
    assert result["volume"] == 3
    assert result["series"] == "batman" or result["title"] == "batman"


def test3():
    result = lex_and_parse(
        "Spider-Boy - Full Circle v01 (2026) (digital) (Marika-Empire)"
    )

    assert result["title"] == "full circle"
    assert result["series"] == "spider-boy"
    assert result["year"] == 2026
    assert result["volume"] == 1


def test4():
    result = lex_and_parse(
        "Guardians of the Galaxy v01 - Cosmic Avengers (2013) (Digital) (F) (Zone-Empire)"
    )

    assert result["series"] == "guardians of the galaxy"
    assert result["title"] == "cosmic avengers"
    assert result["volume"] == 1
    assert result["year"] == 2013


def test5():
    result = lex_and_parse(
        "Justice League - The Atom Project (2025) (digital) (Son of Ultron-Empire)"
    )

    assert result["series"] == "justice league"
    assert result["title"] == "the atom project"
    assert result["volume"] == 1
    assert result["year"] == 2025


def test6():
    result = lex_and_parse(
        "Moon Knight - Fist Of Khonshu - Subterranean Jungle v01 (2026) (digital) (Marika-Empire)"
    )

    assert result["volume"] == 1
    assert result["year"] == 2026
    assert result["series"] == "moon knight fist of khonshu"
    assert result["title"] == "subterranean jungle"


def test7():
    result = lex_and_parse(
        "Doctor Strange Of Asgard v01 (2026) (digital) (Marika-Empire)"
    )

    assert (
        result["series"] == "doctor strange of asgard"
        or result["title"] == "doctor strange of asgard"
    )
    assert result["volume"] == 1
    assert result["year"] == 2026

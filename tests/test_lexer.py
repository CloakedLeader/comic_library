from tagging.itemtypes import LexerType
from tagging.lexer import Lexer


def lex_all(text):
    lex = Lexer(text)
    tokens = []
    lex.run()
    for t in lex.items:
        tokens.append((t.typ, t.val))
    return tokens


def test_single_word():
    tokens = lex_all("Batman")
    assert tokens == [(LexerType.Text, "Batman"), (LexerType.EOF, "")]


def test_word_and_number():
    tokens = lex_all("Flash New 52")
    assert tokens == [
        (LexerType.Text, "Flash"),
        (LexerType.Space, " "),
        (LexerType.Text, "New"),
        (LexerType.Space, " "),
        (LexerType.Number, "52"),
        (LexerType.EOF, ""),
    ]


def test_dash():
    tokens = lex_all("Avengers - Endgame")
    assert tokens == [
        (LexerType.Text, "Avengers"),
        (LexerType.Space, " "),
        (LexerType.Dash, "-"),
        (LexerType.Space, " "),
        (LexerType.Text, "Endgame"),
        (LexerType.EOF, ""),
    ]


def test_apostrophes():
    tokens = lex_all("Spider-Man's Revenge")
    assert tokens == [
        (LexerType.Text, "Spider-Man's"),
        (LexerType.Space, " "),
        (LexerType.Text, "Revenge"),
        (LexerType.EOF, ""),
    ]

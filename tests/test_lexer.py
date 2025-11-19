import pytest

from tagging.itemtypes import LexerItem
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
    assert tokens == [(LexerItem.Text, "Batman"), (LexerItem.EOF, "")]


def test_word_and_number():
    tokens = lex_all("Flash New 52")
    assert tokens == [
        (LexerItem.Text, "Flash"),
        (LexerItem.Space, " "),
        (LexerItem.Text, "New"),
        (LexerItem.Space, " "),
        (LexerItem.Number, "52"),
        (LexerItem.EOF, ""),
    ]


def test_dash():
    tokens = lex_all("Avengers - Endgame")
    assert tokens == [
        (LexerItem.Text, "Avengers"),
        (LexerItem.Space, " "),
        (LexerItem.Dash, "-"),
        (LexerItem.Space, " "),
        (LexerItem.Text, "Endgame"),
        (LexerItem.EOF, ""),
    ]


def test_apostrophes():
    tokens = lex_all("Spider-Man's Revenge")
    assert tokens == [
        (LexerItem.Text, "Spider-Man's"),
        (LexerItem.Space, " "),
        (LexerItem.Text, "Revenge"),
        (LexerItem.EOF, ""),
    ]

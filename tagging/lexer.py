import calendar
import os
import re

from enum import Enum, IntEnum, auto
from pathlib import Path
from typing import Callable, Optional, Protocol
from dotenv import load_dotenv

from itemtypes import Item, ItemType


load_dotenv()
API_KEY = os.getenv("API_KEY")

eof = chr(0)

key = {
    "fcbd": ItemType.FCBD,
    "freecomicbookday": ItemType.FCBD,
    "cbr": ItemType.ArchiveType,
    "cbz": ItemType.ArchiveType,
    "rar": ItemType.ArchiveType,
    "zip": ItemType.ArchiveType,
    "annual": ItemType.ComicType,
    "of": ItemType.InfoSpecifier,
    "dc": ItemType.Publisher,
    "marvel": ItemType.Publisher,
    "covers": ItemType.InfoSpecifier,
    "c2c": ItemType.C2C,
}


def is_numeric_or_number_punctuation(x: str) -> bool:
    digits = "0123456789.,"
    return x.isnumeric() or x in digits


class LexerFunc(Protocol):

    def __call__(self, __origin: "Lexer") -> "LexerFunc | None":
        pass


class Lexer:
    """
    A class to process the filename and extract the different items found.
    """

    def __init__(self, string: str) -> None:
        """
        Creates an instance which tracks a certain string, finds all the Items within it.

        Parameters:
        string: This is the filename to be lexed.

        This runs a state-based lexer that moves through the string and decides how to split
        it up into Items.
        """
        self.input: str = string
        self.state: LexerFunc | None = None
        self.pos: int = -1
        self.start: int = 0
        self.last_pos: int = 0
        self.paren_depth: int = 0
        self.brace_depth: int = 0
        self.sbrace_depth: int = 0
        self.items: list[Item] = []

    def get(self) -> str:
        """
        Gets the next character in the string or returns end of string message
        and adds 1 to position counter.

        Returns:
        The next character in the filename or the null character to indicate end of string.
        """
        if int(self.pos) >= len(self.input) - 1:
            self.pos += 1
            return eof

        self.pos += 1
        return self.input[self.pos]

    def peek(self) -> str:
        """
        Looks at the next character in the string but does not 'consume' it.

        Will be used to 'look' at next character and decide what to do.

        Returns:
        The next character in the string.
        """
        if int(self.pos) >= len(self.input) - 1:
            return eof
        return self.input[self.pos + 1]

    def backup(self) -> None:
        """
        Decreases the position by one, i.e. goes back one character in the string.
        """
        self.pos -= 1

    def emit(self, t: ItemType) -> None:
        """
        Adds the newly found token to the list of tokens and
        updates the start variable ready for the next token.

        Parameters:
        t: The kind of token to be added to the list.
        """
        self.items.append(Item(t, self.start, self.input[self.start : self.pos + 1]))
        self.start = self.pos + 1

    def ignore(self) -> None:
        """
        Ignores anything from the start position until the current position.
        Used to omit whitespaces etc.
        """
        self.start = self.pos

    def accept(self, valid: str | Callable[[str], bool]) -> bool:
        """
        Checks to see if the next character in the lexer instance
        is in a certain string or is a certain type of character.

        Parameter:
        valid [str]: A string to see if the next character
        in the class instance is a substring of valid.
        OR
        valid [Callable]: A function (e.g. isdigit ) that checks if
        the next character returns a truthy value.

        Returns:
        bool = Whether or not the next character in the class
        instance is in the input string or the Callable output.
        """
        if isinstance(valid, str):
            if self.get() in valid:
                return True

        else:
            if valid(self.get()):
                return True

        self.backup()
        return False

    def accept_run(self, valid: str | Callable[[str], bool]) -> bool:
        """
        Tries to accept a sequence of characters that are of the same type/token.

        Parameters:
        valid [str]: A string to see if the next character
        in the class instance is a substring of valid.
        OR
        valid [Callable]: A function (e.g. isdigit ) that checks
        if the next character returns a truthy value.

        Returns:
        bool = Returns whether the position actually moved forward
        or not, so you can consume entire tokens at a time.
        """
        initial = self.pos
        if isinstance(valid, str):
            while self.get() in valid:
                continue
        else:
            while valid(self.get()):
                continue

        self.backup()
        return initial != self.pos

    def scan_number(self) -> bool:
        """
        Checks if a string is numeric and if it has a suffix
        of letters directly after, no whitespace.
        """
        if not self.accept_run(is_numeric_or_number_punctuation):
            return False
        if self.input[self.pos] == ".":
            self.backup()
        self.accept_run(str.isalpha)
        return True

    def run(self) -> None:
        """
        This controls the state-based lexer by keeping the process running as long
        as None isn't returned. 
        """
        self.state = run_lexer
        while self.state is not None:
            self.state = self.state(self)


def errorf(lex: Lexer, message: str) -> None:
    lex.items.append(Item(ItemType.Error, lex.start, message))


def run_lexer(lex: Lexer) -> Optional[LexerFunc]:
    """
    This is where the logic for the seperation of tokens comes from.

    Parameters:
    lex: The Lexer instance which has to be iterated through and turned into
        tokens.

    Returns:
    Either LexerFunc if there is still more to process, or None which terminates
    the lexing process.
    """
    r = lex.get()

    if r == eof:
        lex.emit(ItemType.EOF)
        return None

    elif r.isspace():
        lex.ignore()
        return run_lexer

    elif r.isnumeric():
        lex.backup()
        return lex_number

    elif r == "#":
        if lex.peek().isnumeric():
            return lex_issue_number
        else:
            errorf(lex, "expected number after #")
            return run_lexer

    elif r.lower() == "v":
        if lex.peek().lower() == "o":
            lex.get()  # consume 'o'
        if lex.peek().lower() == "l":
            lex.get()  # consume 'l'
            if lex.peek() == ".":
                lex.get()  # consume '.'
            return lex_volume_number_full
        elif lex.peek().isdigit():
            return lex_volume_number
        else:
            return lex_text

    elif r.lower() == "b":
        lex.backup()
        if lex.input[lex.pos : lex.pos + 3].lower() == "by ":
            lex.start = lex.pos
            lex.pos += 2
            lex.emit(ItemType.InfoSpecifier)
            return lex_author
        lex.get()
        return lex_text

    elif r.lower() in "tophc":
        lex.backup()
        return lex_collection_type

    elif is_alpha_numeric(r):
        lex.backup()
        return lex_text

    elif r == "-":
        lex.emit(ItemType.Separator)
        return run_lexer

    elif r == "(":
        lex.emit(ItemType.LeftParen)
        lex.paren_depth += 1
        return run_lexer

    elif r == ")":
        lex.emit(ItemType.RightParen)
        lex.paren_depth -= 1
        if lex.paren_depth < 0:
            errorf(lex, "unexpected right paren " + r)
            return None
        return run_lexer

    elif r == "{":
        lex.emit(ItemType.LeftBrace)
        lex.brace_depth += 1
        return run_lexer

    elif r == "}":
        lex.emit(ItemType.RightBrace)
        lex.brace_depth -= 1
        if lex.brace_depth < 0:
            errorf(lex, "unexpected right brace " + r)
            return None
        return run_lexer

    elif r == "[":
        lex.emit(ItemType.LeftSBrace)
        lex.sbrace_depth += 1
        return run_lexer

    elif r == "]":
        lex.emit(ItemType.RightSBrace)
        lex.sbrace_depth -= 1
        if lex.sbrace_depth < 0:
            errorf(lex, "unexpected right square brace")
            return None
        return run_lexer
    else:
        errorf(lex, f"unexpected character: {r}")
        return run_lexer


def lex_space(lex: Lexer) -> LexerFunc:
    """
    This consumes a series of whitespaces and emits them.
    """
    if lex.accept_run(is_space):
        lex.emit(ItemType.Space)
    return run_lexer


def lex_text(lex: Lexer) -> LexerFunc:
    """
    This emits a series of letters or number not seperated by a space.
    Then tries to match the word to common words defined in 'key'.
    Finally it decides on the ItemType and emits.
    """
    while True:
        r = lex.get()

        if is_alpha_numeric(r) or r == "'":
            continue
        else:
            lex.backup()
            break
    word = lex.input[lex.start : lex.pos]

    lower_word = word.casefold()
    if lower_word in key:
        token_type = key[lower_word]
        if token_type in (ItemType.Honorific, ItemType.InfoSpecifier):
            lex.accept(".")
        lex.emit(token_type)
    elif cal(word):
        lex.emit(ItemType.Calendar)
    else:
        lex.emit(ItemType.Text)
    return run_lexer


def lex_number(lex: Lexer) -> LexerFunc:
    """
    This emits a series of numbers without any whitespace.
    It also tries to handle common number suffixes.
    Finally emits either a number or, text if there is a suffix.
    """
    if not lex.scan_number():
        errorf(lex, "bad number syntax: " + lex.input[lex.start : lex.pos])
        return run_lexer

    if lex.pos < len(lex.input) and lex.input[lex.pos].isalpha():
        lex.accept_run(str.isalpha)
        lex.emit(ItemType.Text)
        return run_lexer
    lex.emit(ItemType.Number)
    return run_lexer


def lex_issue_number(lex: Lexer) -> LexerFunc:
    """
    This attempts to find the issue number for a comic.
    It is only called if lex.input[lex.start] == "#".
    Finally it emits the run of numbers as type IssueNumber.
    """
    if not lex.peek().isnumeric():
        lex.emit(ItemType.Symbol)
        return run_lexer

    lex.accept_run(str.isdigit)

    lex.accept_run(str.isalpha)

    lex.emit(ItemType.IssueNumber)
    return run_lexer


def lex_author(lex: Lexer) -> LexerFunc:
    """
    This attempts to identify an author in the string.
    
    TODO: Reinforce this code to be better!!
    """
    lex.accept_run(str.isspace)
    name_parts = 0

    while name_parts < 3:
        word_start = lex.pos
        lex.accept_run(str.isalpha)

        word = lex.input[word_start : lex.pos]

        if lex.peek() == ".":
            lex.get()
            word += "."
        if word and (word[0].isupper() or (len(word) == 2 and word[1] == ".")):
            name_parts += 1
        else:
            lex.pos = word_start
            break

        if not lex.accept(" "):
            break

    if name_parts >= 1:
        lex.emit(ItemType.Author)
    else:
        lex.emit(ItemType.Text)

    return run_lexer


def lex_collection_type(lex: Lexer) -> LexerFunc:
    """
    This runs through a string attempts to match it to common collection
    titles as defined in known_collections. If it can't match it, it
    returns the token as Text.
    """
    lex.accept_run(str.isalpha)
    word = lex.input[lex.start : lex.pos].casefold()

    known_collections = {
        "tpb",
        "hc",
        "hardcover",
        "omnibus",
        "deluxe",
        "compendium",
        "digest",
    }

    if word in known_collections:
        lex.emit(ItemType.CollectionType)
    else:
        lex.emit(ItemType.Text)

    return run_lexer


def lex_volume_number(lex: Lexer) -> LexerFunc:
    """
    This attempts to find the volume number in a token, this is called
    when the lexer finds volume signifiers like vol or v.
    """
    lex.accept_run(str.isdigit)

    if lex.pos == lex.start:
        lex.accept_run(is_space)
        lex.accept_run(str.isdigit)

    if lex.pos > lex.start:
        lex.emit(ItemType.VolumeNumber)
    else:
        lex.emit(ItemType.Text)

    return run_lexer


def lex_volume_number_full(lex: Lexer) -> LexerFunc:
    lex.accept_run(is_space)
    if lex.peek().isdigit():
        lex.accept_run(str.isdigit)
        lex.emit(ItemType.VolumeNumber)
    # if lex.pos > lex.start:
    #     lex.emit(ItemType.VolumeNumber)
    else:
        lex.emit(ItemType.Text)

    return run_lexer


def is_space(character: str) -> bool:
    return character.isspace() or character == "_"


def is_alpha_numeric(character: str) -> bool:
    return character.isalpha() or character.isnumeric()


def cal(word: str) -> bool:
    word_lower = word.lower()

    months = [m.lower() for m in calendar.month_name if m] + [
        m.lower() for m in calendar.month_abbr if m
    ]
    if word_lower in months:
        return True

    return bool(re.fullmatch(r"\d{4}", word) or re.fullmatch(r"\d{4}s", word))


def lex(filename: str) -> Lexer:
    lex = Lexer(os.path.basename(filename))
    lex.run()
    return lex

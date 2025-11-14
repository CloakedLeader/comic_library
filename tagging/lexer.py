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
    """
    Determine whether a single character represents a numeric digit or a numeric punctuation character ('.' or ',').
    
    Parameters:
        x (str): A single-character string to test.
    
    Returns:
        bool: True if `x` is a digit or one of `'.'` or `','`, False otherwise.
    """
    digits = "0123456789.,"
    return x.isnumeric() or x in digits


class LexerFunc(Protocol):

    def __call__(self, __origin: "Lexer") -> "LexerFunc | None":
        """
        Execute one lexing step for the provided Lexer and yield the next state.
        
        Parameters:
            __origin (Lexer): The Lexer instance whose state is being executed.
        
        Returns:
            LexerFunc | None: The next state function to continue lexing, or `None` to stop the lexer.
        """
        pass


class Lexer:
    """
    A class to process the filename and extract the different items found.
    """

    def __init__(self, string: str) -> None:
        """
        Initialises the Lexer state for lexing the given filename.
        
        Parameters:
            string (str): The filename (or input string) to be tokenised; stored as the lexer's input.
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
        Advance the lexer's position by one and return the character at the new position.
        
        Returns:
            str: The character at the new position, or the EOF sentinel (null character) when the end of input has been reached.
        """
        if int(self.pos) >= len(self.input) - 1:
            self.pos += 1
            return eof

        self.pos += 1
        return self.input[self.pos]

    def peek(self) -> str:
        """
        Return the next character without advancing the lexer's current position.
        
        Returns:
            The next character from the input, or `eof` if the end of input has been reached.
        """
        if int(self.pos) >= len(self.input) - 1:
            return eof
        return self.input[self.pos + 1]

    def backup(self) -> None:
        """
        Move the lexer's current position back by one character.
        
        This shifts the internal position index earlier in the input so the previously read character will be returned again by the next `get()` call.
        """
        self.pos -= 1

    def emit(self, t: ItemType) -> None:
        """
        Emit a token spanning the input from the current start position up to the current position.
        
        Appends an Item with the given token type and the corresponding substring to the lexer's items list, then advances the lexer's start to the next position.
        
        Parameters:
            t (ItemType): The token type to emit.
        """
        self.items.append(Item(t, self.start, self.input[self.start : self.pos + 1]))
        self.start = self.pos + 1

    def ignore(self) -> None:
        """
        Mark the current lexeme as ignored.
        
        Sets the lexer's start position to the current read position so characters consumed since the previous start are skipped for future token emission.
        """
        self.start = self.pos

    def accept(self, valid: str | Callable[[str], bool]) -> bool:
        """
        Attempt to consume the next character if it matches a given set of characters or a predicate.
        
        If `valid` is a string, the next character is consumed when it is one of the characters in that string.
        If `valid` is a callable, the next character is consumed when the callable returns a truthy value for that character.
        When a character is not accepted the lexer's position is restored.
        
        Parameters:
            valid (str | Callable[[str], bool]): A string of acceptable characters or a predicate that returns truthy for acceptable characters.
        
        Returns:
            bool: `True` if the next character matched and was consumed, `False` otherwise.
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
        Consume a consecutive run of characters that match either a set of allowed characters or a predicate.
        
        Parameters:
            valid (str | Callable[[str], bool]): Either a string whose characters are accepted, or a callable
            that takes a single character and returns truthy if that character is accepted.
        
        Returns:
            bool: `True` if at least one character was consumed, `False` otherwise.
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
        Determine whether the lexer is currently positioned at a number-like token and
        consume it (including an immediate alphabetic suffix, if present).
        
        Consumes a run of digits and numeric punctuation, optionally trims a trailing dot, then
        consumes any immediately following alphabetic characters without intervening whitespace.
        
        Returns:
            `true` if a number-like sequence was found and consumed, `false` otherwise.
        """
        if not self.accept_run(is_numeric_or_number_punctuation):
            return False
        if self.input[self.pos] == ".":
            self.backup()
        self.accept_run(str.isalpha)
        return True

    def run(self) -> None:
        """
        Drive the lexer's state machine until it terminates.
        
        Initialises the current state to `run_lexer` and repeatedly invokes the
        active state function until a state function returns `None`, signalling completion.
        """
        self.state = run_lexer
        while self.state is not None:
            self.state = self.state(self)


def errorf(lex: Lexer, message: str) -> None:
    """
    Record an error item on the lexer with the given message.
    
    Appends an Item of type `Error` to `lex.items`.
    
    Parameters:
    	lex (Lexer): Lexer instance to receive the error item.
    	message (str): Text message stored in the emitted Error item.
    """
    lex.items.append(Item(ItemType.Error, lex.start, message))


def run_lexer(lex: Lexer) -> Optional[LexerFunc]:
    """
    Advance the lexer's state by reading the next character and dispatching to the appropriate lexer state function.
    
    Processes one input character from `lex`, emitting tokens and updating lexer state as required.
    Effects include emitting Item tokens to `lex.items`, adjusting `lex.pos`/`lex.start`,
    and recording errors via `errorf` when encountering unexpected input.
    
    Parameters:
        lex (Lexer): The lexer instance to advance by one step.
    
    Returns:
        LexerFunc | None: The next state function to execute, or `None` to terminate lexing.
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
    Consume a run of whitespace characters and emit a Space token.
    
    Parameters:
        lex (Lexer): The lexer instance to read from and emit tokens to.
    
    Returns:
        LexerFunc: The next lexer state function (`run_lexer`) to continue processing.
    """
    if lex.accept_run(is_space):
        lex.emit(ItemType.Space)
    return run_lexer


def lex_text(lex: Lexer) -> LexerFunc:
    """
    Recognises an alphanumeric or apostrophe-containing word from the lexer's input and emits the corresponding Item token.
    
    Emitted token is:
    - the mapped ItemType when the lowercased word exists in the keyword map (allowing an optional trailing '.' for certain token types),
    - ItemType.Calendar when the word represents a month name or a four-digit year (optionally ending with 's'),
    - otherwise ItemType.Text.
    
    Parameters:
        lex (Lexer): The lexer instance to read from and to which the emitted Item is appended.
    
    Returns:
        LexerFunc: The next lexer state function (run_lexer).
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
    Recognises a numeric token (including numeric punctuation and optional alphabetic suffix) and emits a Number or Text item.
    
    Scans a run of digits and number punctuation; if the run is invalid an Error item is appended. If alphabetic characters immediately follow the numeric run they are consumed and the whole token is emitted as Text; otherwise the token is emitted as Number.
    
    Parameters:
    	lex (Lexer): The lexer instance whose input and state are advanced.
    
    Returns:
    	The next lexer state function to execute, or `None` to stop.
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
    Parse an issue number starting at the current '#' and emit the corresponding token.
    
    If the character after '#' is not a digit, emits a `Symbol` item.
    Otherwise consumes a run of digits plus any immediate alphabetic suffix and emits an `IssueNumber` item.
    
    Parameters:
        lex (Lexer): Lexer instance positioned with `lex.input[lex.start] == '#'`.
    
    Returns:
        The next lexer state function to execute, or `None` to stop.
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
    Attempt to recognise and emit an author-name token at the current lexer position.
    
    Consumes up to three name parts (capitalised words or initials with a trailing period).
    If at least one name part is recognised, emits ItemType.Author; otherwise emits ItemType.Text.
    
    Returns:
    	The next lexer state function to continue lexing.
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
    Recognises a contiguous alphabetic word and classifies it as a collection type or plain text.
    
    Consumes a run of alphabetic characters, lowercases the consumed word and,
    if it matches a known collection token, such as "tpb", "hc", emits an ItemType.CollectionType; otherwise emits ItemType.Text.
    
    Returns:
    	The next lexer state function to execute (typically `run_lexer`).
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
    Parse a volume number following a volume signifier and emit the appropriate token.
    
    If one or more digits are found immediately or after optional spaces, emits an ItemType.VolumeNumber for the consumed run.
    Otherwise emits ItemType.Text.
    
    Returns:
    	The next lexer state function to continue lexing.
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
    """
    Consume optional leading spaces and, if a digit sequence follows, consume it and emit an ItemType.VolumeNumber; otherwise emit ItemType.Text.
    
    Parameters:
    	lex (Lexer): The lexer instance whose input and position are being advanced.
    
    Returns:
    	run_lexer (LexerFunc): The next state function to continue lexing.
    """
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
    """
    Determine whether a character is treated as whitespace by the lexer.
    
    Parameters:
    	character (str): The character to test; underscore ('_') is treated as whitespace.
    
    Returns:
    	True if the character is a Unicode whitespace character or an underscore, False otherwise.
    """
    return character.isspace() or character == "_"


def is_alpha_numeric(character: str) -> bool:
    """
    Check whether the given character is alphabetic or numeric.
    
    Returns:
        `True` if the character is alphabetic or numeric, `False` otherwise.
    """
    return character.isalpha() or character.isnumeric()


def cal(word: str) -> bool:
    """
    Determine whether a token denotes a calendar month name/abbreviation or a four-digit year (optionally followed by 's').
    
    Matches month names and abbreviations case-insensitively (e.g. "January", "Jan"), or strings of the form "YYYY" or "YYYYs" (e.g. "2023", "1990s").
    
    Parameters:
        word (str): The token to test.
    
    Returns:
        True if the token is a month name/abbreviation or a 4-digit year optionally suffixed with 's', False otherwise.
    """
    word_lower = word.lower()

    months = [m.lower() for m in calendar.month_name if m] + [
        m.lower() for m in calendar.month_abbr if m
    ]
    if word_lower in months:
        return True

    return bool(re.fullmatch(r"\d{4}", word) or re.fullmatch(r"\d{4}s", word))


def lex(filename: str) -> Lexer:
    """
    Tokenise the basename of a filename into a Lexer populated with Item tokens.
    
    Parameters:
        filename (str): Path or filename to lex; only the basename is tokenised.
    
    Returns:
        lex (Lexer): A Lexer instance whose `items` list contains the tokens produced from the filename.
    """
    lex = Lexer(os.path.basename(filename))
    lex.run()
    return lex

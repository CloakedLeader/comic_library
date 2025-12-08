import calendar
import os
import re
from typing import Callable, Optional, Protocol

from dotenv import load_dotenv

from .itemtypes import Item, LexerType, ParserType

load_dotenv()
API_KEY = os.getenv("API_KEY")

eof = chr(0)

key = {
    "fcbd": ParserType.FCBD,
    "freecomicbookday": ParserType.FCBD,
    "cbr": ParserType.ArchiveType,
    "cbz": ParserType.ArchiveType,
    "rar": ParserType.ArchiveType,
    "zip": ParserType.ArchiveType,
    "annual": ParserType.ComicType,
    "of": ParserType.InfoSpecifier,
    "dc": ParserType.Publisher,
    "marvel": ParserType.Publisher,
    "covers": ParserType.InfoSpecifier,
    "c2c": ParserType.C2C,
}


def is_numeric_or_number_punctuation(x: str) -> bool:
    """
    Determine whether a single character represents a numeric digit or
       a numeric punctutaion character('.' or ',').

    Args:
        x (str): A single character to test.

    Returns:
        bool: True if 'x' belongs in a number token. False otherwise.
    """
    digits = "0123456789.,"
    return x.isnumeric() or x in digits


class LexerFunc(Protocol):
    def __call__(self, __origin: "Lexer") -> "LexerFunc | None":
        """
        Execute one lexing step for the provided Lexer and yield the
            next state.

        Args:
            __origin (Lexer): The Lexer instance whose state is being
                executed.

        Returns:
            LexerFunc | None: The next state function to continue lexing,
                or Nonee to stop the Lexer.
        """
        pass


class Lexer:
    """
    A class to process the filename and extract the different items found.
    """

    def __init__(self, string: str) -> None:
        """
        Intialises the Lexer state for lexing the given filename.

        Args:
            string (str): The filename (or input string) to be tokenised, stored
                as the lexer's input.
        """

        self.input: str = string
        self.state: LexerFunc | None = None
        self.pos: int = 0
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
            str: The character at the new position, or the EOF sentinel when the end of the
                input has been reached.
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
            str: The next character from the input, or 'eof' if the end of the input
                has been reached.
        """

        if int(self.pos) >= len(self.input) - 1:
            return eof
        return self.input[self.pos + 1]

    def backup(self) -> None:
        """
        Move the lexer's current position back by one character.

        This shifts the internal index earlier in the input so the previously read character
            will be returned again by the next 'get()' call.
        """

        self.pos -= 1

    def emit(self, t: LexerType) -> None:
        """
        Emit a token spanning the input from the current start position up to the current position.

        Appends an Item with the given token type and the corresponding substring to the
            lexer's items list, then advances the lexer's start to the next position.
        Args:
            t (ItemType): The token type to emit.
        """

        self.items.append(Item(t, self.start, self.input[self.start : self.pos + 1]))
        self.start = self.pos + 1

    def ignore(self) -> None:
        """
        Mark the current lexeme as ignored.

        Sets the lexer's start position to the current read position so character's consumed since
            the previous start are skipped for future token emission.
        """

        self.start = self.pos

    def accept(self, valid: str | Callable[[str], bool]) -> bool:
        """
        Attempt to consume the next character if it matches a given set of characters or a predicate.

        If 'valid' is a string, the next character is consumed when it is one of the characters in
            that string.
        If 'valid' is a callable, the next character is consumed when the callable returns a truthy
            value for that character.
        When a character is not accepted the lexer's position is restored.

        Args:
            valid (str | Callable[[str], bool]): A string of acceptable characters or a predicate
                that returns truthy for acceptable characters.

        Returns:
            bool: Whether the character follows the rules from above.
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
        Consume a consecutive run of characters that match either a set of allowed characters or
            a predicate.

        Args:
            valid (str | Callable[[str], bool]): Either a string whose characters are acceptable,
                or a callable that returns truthy for acceptable characters.

        Returns:
            bool: Whether the run of characters follow the rules from above.
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
        Determine whether the lexer is currently positioned at a number-like token and consume
            it.

        Consumes a run of digits and numeric punctuation, optionally trims a trailing dot, then
            consumes any immediately following alphabetic characters without intermediate whitespace.

        Returns:
            bool: 'True' if a number-like sequence was found, 'false' otherwise.
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

        Intialises the current state to 'run_lexer' and repeatedly invokes the active state function
            until a state function returns None, signalling completion.
        """

        self.state = run_lexer
        while self.state is not None:
            self.state = self.state(self)


def errorf(lex: Lexer, message: str) -> None:
    """
    Record an error item on the lexer with the given message.

    Args:
        lex (Lexer): Lexer instance to receive the error item.
        message (str): Text message stored in the emitted Error item.
    """
    lex.items.append(Item(LexerType.Error, lex.start, message))


def run_lexer(lex: Lexer) -> Optional[LexerFunc]:
    """
    Advance the lexer's state by reading the next character and dispatching to the
        appropriate lexer state function.
    Processes one input character from 'lex', emitting tokens and updating state function
        as required.

    Args:
        lex (Lexer): The lexer instance to advance by one step.

    Returns:
        Optional[LexerFunc]: The next state function to execute, or None to terminate
            lexing.
    """

    r = lex.get()

    if r == eof:
        lex.emit(LexerType.EOF)
        return None

    elif is_space(r):
        lex.backup()
        return lex_space

    elif r.isnumeric():
        lex.backup()
        return lex_number

    elif r.isalpha():
        lex.backup()
        return lex_text

    elif r == "-":
        lex.emit(LexerType.Dash)
        return run_lexer

    elif r == ".":
        lex.emit(LexerType.Dot)
        return run_lexer

    elif r == "(":
        lex.emit(LexerType.LeftParen)
        lex.paren_depth += 1
        return run_lexer

    elif r == ")":
        lex.emit(LexerType.RightParen)
        lex.paren_depth -= 1
        if lex.paren_depth < 0:
            errorf(lex, "unexpected right paren " + r)
            return None
        return run_lexer

    elif r == "{":
        lex.emit(LexerType.LeftBrace)
        lex.brace_depth += 1
        return run_lexer

    elif r == "}":
        lex.emit(LexerType.RightBrace)
        lex.brace_depth -= 1
        if lex.brace_depth < 0:
            errorf(lex, "unexpected right brace " + r)
            return None
        return run_lexer

    elif r == "[":
        lex.emit(LexerType.LeftBracket)
        lex.sbrace_depth += 1
        return run_lexer

    elif r == "]":
        lex.emit(LexerType.RightBracket)
        lex.sbrace_depth -= 1
        if lex.sbrace_depth < 0:
            errorf(lex, "unexpected right square brace")
            return None
        return run_lexer

    elif r in "#&:+/;!?":
        lex.emit(LexerType.Symbol)
        return run_lexer

    else:
        errorf(lex, f"unexpected character: {r}")
        return run_lexer


def lex_space(lex: Lexer) -> LexerFunc:
    """
    Consume a run of whitespace characters and emit a Space token.

    Args:
        lex (Lexer): The lexer instance to read from and emit tokens to.

    Returns:
        LexerFunc: The next state function 'run_lexer' to continue processing.
    """

    while True:
        r = lex.get()
        if r.isspace() or r == "_":
            continue
        else:
            lex.backup()
            break

    lex.emit(LexerType.Space)
    return run_lexer


def lex_text(lex: Lexer) -> LexerFunc:
    """
    Recognises an alphanumeric or apostrophe-containing workd from the lexer's input
        and emits the corresponding Item type.

    Args:
        lex (Lexer): The lexer instance to read from and to which the emitted Item is appended.

    Returns:
        LexerFunc: The next lexer state function.
    """

    while True:
        r = lex.get()
        if not r:
            break

        if len(r) == 1 and (r.isalnum() or r == "'" or r == "-"):
            continue

        else:
            lex.backup()
            break

    lex.emit(LexerType.Text)
    return run_lexer


def lex_number(lex: Lexer) -> LexerFunc:
    """
    Recognises a numeric token and emits a Number or Text Item.

    Args:
        lex (Lexer): The lexer instance whose input and state are advanced.

    Returns:
        LexerFunc: The next lexer state function to execute or None to terminate.
    """

    while True:
        r = lex.get()
        if r.isdigit():
            continue
        else:
            lex.backup()
            break

    lex.emit(LexerType.Number)
    return run_lexer


def is_space(character: str) -> bool:
    """
    Determine whether a character is treated as a whitespace by the lexer.

    Args:
        character (str): The character to test.

    Returns:
        bool: True if the character is effectively whitespace. False otherwise.
    """

    return character.isspace() or character == "_"


def is_alpha_numeric(character: str) -> bool:
    """
    Check whether the given character is alphabetic or numeric.

    Args:
        character (str): The character to test.

    Returns:
        bool: True if the character is alphanumeric. False otherwise.
    """

    return character.isalpha() or character.isnumeric()


def cal(word: str) -> bool:
    """
    Determine whether a token denotes a calendar month name/abbreviation or a 4
    digit year.

    Args:
        word (str): The token to test.

    Returns:
        bool: True if the token is a month or year token. False otherwise.
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
    Tokenise the basename of the filename into a Lexer populated with Item tokens.

    Args:
        filename (str): Path or filename to lex, only the basename is tokenised.

    Returns:
        Lexer: A Lexer instance whose 'items' list contains the tokens produced from
            the filename.
    """

    lex = Lexer(os.path.basename(filename))
    lex.run()
    return lex

import calendar
import os
import re
from typing import Callable, Optional, Protocol

from dotenv import load_dotenv

from .itemtypes import Item, ItemType

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

    def emit(self, t: ItemType) -> None:
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
    lex.items.append(Item(ItemType.Error, lex.start, message))


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
        lex.emit(ItemType.EOF)
        return None

    elif is_space(r):
        return lex_space

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

    Args:
        lex (Lexer): The lexer instance to read from and emit tokens to.

    Returns:
        LexerFunc: The next state function 'run_lexer' to continue processing.
    """

    if lex.accept_run(is_space):
        lex.emit(ItemType.Space)
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

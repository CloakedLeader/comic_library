
import os
import xml.etree.ElementTree as ET
from typing import Optional, Union, Tuple, List, Dict, Callable, Protocol
from fuzzywuzzy import fuzz
import sys
import time
import re
import calendar
from word2number import w2n
from dotenv import load_dotenv
from file_utils import get_name
from enum import Enum, auto
import unicodedata
from itertools import chain


api_key = os.getenv("API_KEY")

#==================================
#   Filname Lexing
#==================================

def is_numeric_or_digit(x: str) -> bool:
    digits = "0123456789.,"
    return x.isnumeric() or x in digits


class ItemType(Enum):
    Error = auto()
    EOF = auto()
    Text = auto()
    LeftParen = auto()
    Number = auto()  
    IssueNumber = auto()
    RightParen = auto()
    Space = auto() 
    Dot = auto()
    LeftBrace = auto()
    RightBrace = auto()
    LeftSBrace = auto()
    RightSBrace = auto()
    Symbol = auto()
    Skip = auto() 
    Operator = auto()
    Calendar = auto()
    InfoSpecifier = auto() 
    Honorific = auto()
    ArchiveType = auto()
    Publisher = auto()
    Keywords = auto()
    FCBD = auto()
    ComicType = auto()
    C2C = auto()

braces = [
    ItemType.LeftBrace,
    ItemType.LeftParen,
    ItemType.LeftSBrace,
    ItemType.RightBrace,
    ItemType.RightParen,
    ItemType.RightSBrace,
]

eof = chr(0)

key = {
    "fcbd": ItemType.FCBD,
    "freecomicbookday": ItemType.FCBD,
    "cbr": ItemType.ArchiveType,
    "cbz": ItemType.ArchiveType,
    "rar": ItemType.ArchiveType,
    "zip": ItemType.ArchiveType,
    "annual": ItemType.ComicType,
    "volume": ItemType.InfoSpecifier,
    "vol.": ItemType.InfoSpecifier,
    "vol": ItemType.InfoSpecifier,
    "v": ItemType.InfoSpecifier,
    "of": ItemType.InfoSpecifier,
    "dc": ItemType.Publisher,
    "marvel": ItemType.Publisher,
    "covers": ItemType.InfoSpecifier,
    "c2c": ItemType.C2C,
}
    

class Item:
    
    def __init__( self, typ: ItemType, pos: int, val: str ) -> None:
        """
        Creates a new item which has been found in the string.

        Parameters:
        ty [ItemType] = The type defined above e.g. text or parenthesis.
        pos [int] = The position of the first character in the item.
        val [str] = The string representation of the token extracted
        
        """
        self.typ: ItemType = typ
        self.pos: int = pos
        self.val: str = val
        self.no_space = False

    def __repr__( self ) -> str:
        return f"{ self.val }: index: { self.pos }: { self.typ }"
    

class LexerFunc( Protocol ):
    
    def __call__( self, __origin: Lexer) -> LexerFunc | None: ... # type: ignore


class Lexer:
    
    def __init__( self, string: str, allow_issue_start_with_letter: bool = False) -> None:
        self.input: str = string
        self.state: LexerFunc | None = None
        self.pos: int = -1
        self.start: int = 0
        self.lastPos: int = 0 
        self.paren_depth: int = 0  
        self.brace_depth: int = 0  
        self.sbrace_depth: int = 0  
        self.items: list[Item] = []
        self.allow_issue_start_with_letter = allow_issue_start_with_letter


    def get( self ) -> str:
        """
        Gets the next character in the string or returns end of string message and adds 1 to position counter.

        Parameters:
        self = the filemame to be lexed

        Returns:
        str = the next character in the filename, or the null character to indicate end of string. 
        """
        if int( self.pos ) >= len( self.input ) - 1:
            self.pos += 1
            return eof
        
        self.pos += 1
        return self.input[self.pos]
    
        
    def peek( self ) -> str:
        """
        Looks at the next character in the string but does not 'consume' it.
        
        Will be used to 'look' at next character and decide what to do. 

        Parameters:
        self = the filename to be lexed.

        Return:
        str = the next character in the string.
        
        """
        if int( self.pos ) >= len ( self.input ) - 1:
            return eof
        return self.input[ self.pos + 1 ]


    def backup( self ) -> None: 
        # Decreases the position by one, i.e. goes back one character in the string.
        self.pos -= 1


    def emit( self, t: ItemType ) -> None:
        """
        Adds the newly found token to the list of tokens and updates the start variable ready for the next token.

        Parameters:
        t [ItemType] = the kind of token to be added to the list.

        """
        self.items.append( Item( t, self.start, self.input[ self.start : self.pos + 1 ] ) )
        self.start = self.pos + 1


    def ignore( self ) -> None:
        # Ignores anything from the start position until the current position, used to omit whitespaces etc. 
        self.start = self.pos


    def accept( self, valid: str | Callable[ [ str ], bool ] ) -> bool:
        """
        Checks to see if the next character in the lexer instance is in a certain string or is a certain type of character.

        Parameter:
        valid [str] = A string to see if the next character in the class instance is a substring of valid
        OR
        valid [Callable] = A function (e.g. isdigit ) that checks if the next character returns a truthy value

        Returns:
        bool = Whether or not the next character in the class instance is in the input string or function
        """
        if isinstance( valid, str ):
            if self.get() in valid:
                return True
        
        else:
            if valid( self.get() ):
                return True
            
        self.backup()
        return False
    

    def accept_run( self, valid: str | Callable[ [ str ], bool ] ) -> bool:
        """
        Tries to accept a sequence of characters that are of the same type/token.

        Parameters:
        valid [str] = A string to see if the next character in the class instance is a substring of valid
        OR
        valid [Callable] = A function (e.g. isdigit ) that checks if the next character returns a truthy value

        Returns:
        bool = Returns whether the position actually moved forward or not, so you can consume entire tokens at a time.
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
        Checks if a string is numeric and if it has a suffix of letters directly after, no whitespace.
        """
        if not self.accept_run(is_numeric_or_digit):
            return False
        if self.input[self.pos] == ".":
            self.backup()
        self.accept_run(str.isalpha)
        return True
    
    def run(self) -> None:
        # Keeps the lexer process running
        self.state = lex_filename
        while self.state is not None:
            self.state = self.state(self)


def errorf(lex: Lexer, message: str):
    lex.items.append(Item(ItemType.Error, lex.start, message))
    return None


def lex_filename(lex: Lexer) -> LexerFunc | None:
    r = lex.get()
    if r == eof:
        if lex.paren_depth != 0:
            errorf(lex, "unclosed left paren")
            return None
        if lex.brace_depth != 0:
            errorf(lex, "unclosed left paren")
            return None
        lex.emit(ItemType.EOF)
        return None
    elif is_space(r):
        if r == "_" and lex.peek == "_":
            lex.get()
            lex.emit(ItemType.Skip)
        else:
            return lex_space
    elif r == ".":
        r = lex.peek()
        if r.isnumeric() and lex.pos > 0 and is_space(lex.input[lex.pos - 1]):
            return lex_number
        lex.emit(ItemType.Dot)
        return lex_filename
    elif r == "'":
        r = lex.peek()
        if r.isdigit():
            return lex_number
        if is_symbol(r):
            lex.accept_run(is_symbol)
            lex.emit(ItemType.Symbol)
        else:
            return lex_text
    elif r.isnumeric():
        lex.backup()
        return lex_number
    elif r == "#":
        if lex.allow_issue_start_with_letter and is_alpha_numeric(lex.peek()):
            return lex_issue_number
        elif lex.peek().isnumeric() or lex.peek() in "-+.":
            return lex_issue_number
        lex.emit(ItemType.Symbol)
    elif is_operator(r):
        if r == "-" and lex.peek() == "-":
            lex.get()
            lex.emit(ItemType.Skip)
        else:
            return lex_operator
    elif is_alpha_numeric(r):
        lex.backup()
        return lex_text
    elif r == "(":
        lex.emit(ItemType.LeftParen)
        lex.paren_depth += 1
    elif r == ")":
        lex.emit(ItemType.RightParen)
        lex.paren_depth -= 1
        if lex.paren_depth < 0:
            errorf(lex, "unexpected right paren " + r)
            return None
    elif r == "{":
        lex.emit(ItemType.LeftBrace)
        lex.brace_depth += 1
    elif r == "}":
        lex.emit(ItemType.RightBrace)
        lex.brace_depth -= 1
        if lex.brace_depth < 0:
            errorf(lex, "unexpected right brace " + r)
            return None
        

def lex_currency(lex: Lexer) -> LexerFunc:
    orig = lex.pos
    lex.accept_run(is_space)
    if lex.peek().isnumeric():
        return lex_number
    else:
        lex.pos = orig
        lex.emit(ItemType.Symbol)
        return lex_filename
    
def lex_operator(lex: Lexer) -> LexerFunc:
    lex.accept_run("-|:;")
    lex.emit(ItemType.Operator)
    return lex_filename
    

def lex_space(lex: Lexer) -> LexerFunc:
    lex.accept_run(is_space)

    lex.emit(ItemType.Space)
    return lex_filename


def lex_text(lex: Lexer) -> LexerFunc:
    while True:
        r = lex.get()
        if is_alpha_numeric(r) or r in "'":
            if r.isnumeric():  # E.g. v1
                word = lex.input[lex.start : lex.pos]
                if key.get(word.casefold(), None) == ItemType.InfoSpecifier:
                    lex.backup()
                    lex.emit(key[word.casefold()])
                    return lex_filename
        else:
            lex.backup()
            word = lex.input[lex.start : lex.pos + 1]

            if word.casefold() in key:
                if key[word.casefold()] in (ItemType.Honorific, ItemType.InfoSpecifier):
                    lex.accept(".")
                lex.emit(key[word.casefold()])
            elif cal(word):
                lex.emit(ItemType.Calendar)
            else:
                lex.emit(ItemType.Text)
            break

    return lex_filename

def cal(value: str) -> bool:
    return value.title() in set(chain(calendar.month_abbr, calendar.month_name, calendar.day_abbr, calendar.day_name))


def lex_number(lex: Lexer) -> LexerFunc | None:
    if not lex.scan_number():
        return errorf(lex, "bad number syntax: " + lex.input[lex.start : lex.pos])
    # Complex number logic removed. Messes with math operations without space

    if lex.input[lex.start] == "#":
        lex.emit(ItemType.IssueNumber)
    elif not lex.input[lex.pos].isnumeric():
        # Assume that 80th is just text and not a number
        lex.emit(ItemType.Text)
    else:
        # Used to check for a '$'
        endNumber = lex.pos

        # Consume any spaces
        lex.accept_run(is_space)

        # This number starts with a '$' emit it as Text instead of a Number
        if "Sc" == unicodedata.category(lex.input[lex.start]):
            lex.pos = endNumber
            lex.emit(ItemType.Text)

        # This number ends in a '$' if there is a number on the other side we assume it belongs to the following number
        elif "Sc" == unicodedata.category(lex.get()):
            # Store the end of the number '$'. We still need to check to see if there is a number coming up
            endCurrency = lex.pos
            # Consume any spaces
            lex.accept_run(is_space)

            # This is a number
            if lex.peek().isnumeric():
                # We go back to the original number before the '$' and emit a number
                lex.pos = endNumber
                lex.emit(ItemType.Number)
            else:
                # There was no following number, reset to the '$' and emit a number
                lex.pos = endCurrency
                lex.emit(ItemType.Text)
        else:
            # We go back to the original number there is no '$'
            lex.pos = endNumber
            lex.emit(ItemType.Number)

    return lex_filename


def lex_issue_number(lex: Lexer) -> LexerFunc:
    # Only called when lex.input[lex.start] == "#"
    original_start = lex.pos
    lex.accept_run(str.isalpha)

    if lex.peek().isnumeric():
        return lex_number
    else:
        lex.pos = original_start
        lex.emit(ItemType.Symbol)

    return lex_filename


def is_space(character: str) -> bool:
    return character in "_ \t"

def is_alpha_numeric(character: str) -> bool:
    return character.isalpha() or character.isnumeric()

def is_operator(character: str) -> bool:
    return character in "-|:;/\\"

def is_symbol(character: str) -> bool:
    return unicodedata.category(character)[0] in "PS" and character != "."

def Lex(filename: str, allow_issue_start_with_letter: bool = False) -> Lexer:
    lex = Lexer(os.path.basename(filename), allow_issue_start_with_letter)
    lex.run()
    return lex

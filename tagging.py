import requests
import os
import zipfile
import xml.etree.ElementTree as ET
import sqlite3
from typing import Optional, Union, Tuple, List, Dict, Callable, Protocol
from fuzzywuzzy import fuzz
import sys
import time
import re
from word2number import w2n
from dotenv import load_dotenv
from file_utils import get_name
from dataclasses import dataclass
from enum import Enum, auto
import unicodedata


api_key = os.getenv("API_KEY")

def parse_comic_filename(path: str) -> Dict[str, Optional[str]]:
    filename = get_name(path)
    name = filename.rsplit('.', 1)[0]
    pattern = r"""
                ^(?P<series>.+?)                #series name
                (?:\s+v(?P<volume>\d+))?        #optional volume like v01
                (?:\s*-\s*(?P<title>.*?))?      #optional title after dash
                (?:\s+(?P<issue>\d{3}))?        #optional issue number
                \s+\((?P<year>\d{4})\)$         #year in parenthesis at the end
                """
    
    match = re.match(pattern, name, re.VERBOSE)
    if not match:
        return {}
    
    groups = match.groupdict()

    for field in ['volume', 'issue', 'year']:
        if groups[field]:
            groups[field] = int(groups[field])

    return groups
        
path1 = r"comic_pwa/comic_folder/wildcats v1 047 (1998) 22p [image].cbz"

booster_1 = parse_comic_filename(path1)

print(booster_1)

#==================================
#   Filname Lexing
#==================================

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
    ArchiveType = auto()
    Honorific = auto()
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
    "cbt": ItemType.ArchiveType,
    "cb7": ItemType.ArchiveType,
    "rar": ItemType.ArchiveType,
    "zip": ItemType.ArchiveType,
    "tar": ItemType.ArchiveType,
    "7z": ItemType.ArchiveType,
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
    "mr": ItemType.Honorific,
    "ms": ItemType.Honorific,
    "mrs": ItemType.Honorific,
    "dr": ItemType.Honorific,
}

class Item:
    
    def __init__( self, typ: ItemType, pos: int, val: str ) -> None:
        self.typ: ItemType = typ
        self.pos: int = pos
        self.val: str = val
        self.no_space = False

    def __repr__( self ) -> str:
        return f"{ self.val }: index: { self.pos }: { self.typ }"
    

class LexerFunc( Protocol ):
    
    def __call__( self, __origin: Lexer) -> LexerFunc | None: ...


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
        if int( self.pos ) >= len( self.input) - 1:
            self.pos += 1
            return eof
        
    def peek( self ) -> str:
        if int( self.pos ) >= len ( self.input ) - 1:
            return eof
        return self.input[ self.pos + 1 ]

    def backup( self ) -> None:
        self.pos -= 1

    def emit( self, t: ItemType ) -> None:
        self.items.append( Item( t, self.start, self.input[ self.start : self.pos + 1 ] ) )
        self.start = self.pos + 1

    def ignore( self ) -> None:
        self.start = self.pos

    def accept( self, valid: str | Callable[ [ str ], bool ] ):
        if isinstance( valid, str ):
            if self.get() in valid:
                return True
        
        else:
            if valid( self.get() ):
                return True
            
        self.backup()
        return False
    
    def accept_run( self, valid: str | Callable[ [ str ], bool ] ):
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
        digits = "0123456789.,"
        
        if not self.accept_run(lambda x: x.isnumeric() or x in digits):
            return False
        if self.input[self.pos] == ".":
            self.backup()
        self.accept_run(str.isalpha)
        return True
    
    def run(self) -> None:
        self.state = lex_filename
        while self.state is not None:
            self.state = self.state(self)


def errorf(lex: Lexer, message: str):
    lex.items.append(Item(ItemType.Error, lex.start, message))

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




           
        
           



            










































@dataclass
class parsed_filename:
    series_name: str
    collection_type: Optional[str]
    title: Optional[str]
    volume_number: Optional[int]
    year: Optional[int]
        
class filename_parser:
    primary_pattern = re.compile(
        r'^(?P<series>.+?)'
        r'(?:\s+by\s+(?P<writer>[A-Za-z]+))?'
        r'(?P<year>\d{4})?'
        r'\s*-\s*'
        r'(?P<type>[A-Z]+)'
        r'\s+(?P<volume>\d+)'
        r'\s*\((?P<month>\d{2})-(?P<release_year>\d{4})\)'
        r'\.cbz$', re.IGNORECASE
    )
    fallback_pattern = re.compile(
        r'^(?P<series>.+?)'
        r'(?:\s+v(?P<volume>\d+))?'
        r'(?:\s*\((?P<release_year>\d{4})\))?'
        r'\.cbz$', re.IGNORECASE
    )

    def __init__(self, filename: str):
        self.filename = filename
        
    def parse(self) -> Optional[parsed_filename]:
        match = self.primary_pattern.match(self.filename)
        if match:
            return self.build_result(match)
        match = self.fallback_pattern.match(self.filename)
        if match:
            return self.apply_heuristics(match)
        return None
    
    def build_result(self, match: re.Match) -> parsed_filename:
        g = match.groupdict()
        return parsed_filename(
            series_name = g['series'].strip(),
            collection_type = g.get('type', '').upper(),
            volume_number = int(g['volume']) if g.get('volume') else None,
            year = int(g['release_year']) if g.get('release_year') else None
        )   
    
    def apply_heuristics(self, match: re.Match) -> parsed_filename:
        f = match.groupdict()
        guessed_type = "TPB" if "tpb" in self.filename.lower() else None,
        guessed_volume = int(f['volume']) if f.get('volume') else 1,
        guessed_series = f['series'].strip(),
        guessed_year = int(f['release_year']) if f.get('release_year') else None

        return parsed_filename(
            series_name = guessed_series,
            collection_type = guessed_type,
            volume_number = guessed_volume,
            year = guessed_year
            )
    


test1 = filename_parser("Spider-Man - Return of The Black Cat 001 (2010)")
print(test1.parse)

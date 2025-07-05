from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable


class TokenType( Enum ):
    TEXT = auto()
    BRACKET = auto()
    SYMBOL = auto()
    FILETYPE = auto()
    NUMBER = auto()
    DASH = auto()
    Error = auto()
    EOF = auto()
    ISSUENUMBER = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    position: int


end = chr(0)

class Lexer:

    def __init__( self, filename: str ) -> None:
        self.input: str = filename
        self.state: Callable = None
        self.position: int = -1
        self.start: int = 0
        self.paren_depth: int = 0
        self.brace_depth: int = 0
        self.items: list = []

    def get( self ) -> str:
        if int( self.position ) >= len( self.input ) - 1:
            self.position += 1
            return end
        else:
            self.position += 1
        return self.input[ self.position ]
    
    def peek( self ) -> str:
        if int( self.position ) >= len( self.input ) - 1:
            return end
        else: 
            return self.input[ self.position + 1 ]
    
    def backup( self ) -> None:
        self.position -= 1

    def log( self, type: TokenType ) -> None:
        thing_to_log = self.input[ self.start : self.position + 1 ] #I'm not sure this captures the correct part of the string
        self.items.append(Token( type, thing_to_log, self.start))

    def ignore( self ) -> None:
        self.start = self.position

    def accept_character( self, valid: str | Callable[ [ str ], bool ] ) -> bool:
        if isinstance(valid, str):
            if self.get() in valid:
                return True
        elif callable(valid):
            if valid(self.get()):
                return True
        self.backup()
        return False
        
    def accept_run( self, valid: str | Callable[ [ str ], bool ] ) -> bool:
        start = self.position
        if isinstance(valid, str):
            while self.get() in valid:
                continue
        elif callable(valid):
            while valid(self.get()):
                continue
        self.backup()
        return self.position != start
        
    def run_lexer( self ) -> None:
        self.state = lex_start
        while self.state is not None:
            self.state = self.state(self)

def lex_start( lex: Lexer ):
    ch = lex.get()
    if ch == end:
        return None
    





                         
    
    

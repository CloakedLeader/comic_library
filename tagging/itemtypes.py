from enum import Enum, auto


class QMode(Enum):
    COMBO = auto()
    SERIES = auto()
    TITLE = auto()


class LexerItem(Enum):
    EOF = auto()
    Error = auto()

    Text = auto()
    Number = auto()
    Space = auto()

    Dash = auto()
    Dot = auto()
    Symbol = auto()

    LeftParen = auto()
    RightParen = auto()

    LeftBracket = auto()
    RightBracket = auto()

    LeftBrace = auto()
    RightBrace = auto()


class ItemType(Enum):
    Error = auto()
    EOF = auto()
    Text = auto()
    LeftParen = auto()
    Number = auto()
    IssueNumber = auto()
    VolumeNumber = auto()
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
    Author = auto()
    FCBD = auto()
    ComicType = auto()
    CollectionType = auto()
    C2C = auto()
    Separator = auto()


braces = [
    ItemType.LeftBrace,
    ItemType.LeftParen,
    ItemType.LeftSBrace,
    ItemType.RightBrace,
    ItemType.RightParen,
    ItemType.RightSBrace,
]


class Item:
    def __init__(self, typ: LexerItem, pos: int, val: str) -> None:
        """
        Intialise an Item representing a token lexed from an input string.

        Args:
            typ (LexerItem): Token type.
            pos (int): Zero-based index of the token's first character in
                the source string.
            val (str): Exact substring captured for the token.
        """
        self.typ: LexerItem = typ
        self.pos: int = pos
        self.val: str = val
        self.no_space = False

    def __repr__(self) -> str:
        """
        Produce a concise debug-friendly representation of the item.

        Returns:
            str: String formatted version of the token.
        """
        return f"{self.val}: index: {self.pos}: {self.typ}"

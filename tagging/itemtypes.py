from enum import Enum, auto


class QMode(Enum):
    COMBO = auto()
    SERIES = auto()
    TITLE = auto()


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

    def __init__(self, typ: ItemType, pos: int, val: str) -> None:
        """
        Initialise an Item representing a token parsed from an input string.
        
        Parameters:
            typ (ItemType): Token type.
            pos (int): Zero-based index of the token's first character in the source string.
            val (str): Exact substring captured for the token.
        """
        self.typ: ItemType = typ
        self.pos: int = pos
        self.val: str = val
        self.no_space = False

    def __repr__(self) -> str:
        """
        Produce a concise debug-friendly representation of the item.
        
        Returns:
            str: String formatted as "<val>: index: <pos>: <typ>", where `<val>` is the token value, `<pos>` is its start position and `<typ>` is its ItemType.
        """
        return f"{self.val}: index: {self.pos}: {self.typ}"
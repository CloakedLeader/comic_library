import re
from typing import Optional, TypedDict

from .itemtypes import Item, LexerType, ParserType

class FilenameMetadata(TypedDict):
    title: str
    volume_number: int
    series: Optional[str]
    issue_number: Optional[int]
    collection_type: Optional[int]
    year: Optional[int]
    month: Optional[int]


class Parser:
    def __init__(self, tokens: list[Item]):
        self.tokens = tokens
        self.pos = 0

    def current(self) -> Item:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Item(LexerType.EOF, val="", pos=self.pos)
    
    def peek(self, n=1) -> Item:
        new_pos = self.pos + n
        if new_pos < len(self.tokens):
            return self.tokens[new_pos]
        return Item(LexerType.EOF, val="", pos=new_pos)
    
    def prev(self, n=1) -> Item:
        new_pos = self.pos - n
        if new_pos >= 0:
            return self.tokens[new_pos]
        return Item(LexerType.EOF, val="", pos=new_pos)
    
    def next(self, n=1) -> Item:
        token = self.current()
        self.pos += 1
        return token
    
    def try_parse_date_in_paren(self) -> Optional[int]:
        if self.peek() == LexerType.EOF:
            return None
        maybe_year = self.peek()
        if maybe_year.typ == LexerType.Number or len(maybe_year.val) == 4:
            if self.peek(2).typ == LexerType.RightParen:
                year_tok = maybe_year.val
                self.next(); self.next()
                return int(year_tok)
        return None
        

    def parse(self) -> FilenameMetadata:
        
        title_parts: list[str] = []

        while True:
            tok = self.current()

            if tok.typ == LexerType.EOF:
                break

            if tok.typ == LexerType.LeftParen:
                maybe_date = self.try_parse_date_in_paren()
                if maybe_date:
                    metadata_year = maybe_date
                    continue

                title_parts.append(tok.val)
                self.next()
                continue
        pass


# class Parser:
#     def __init__(self, list_of_tokens: list[Item]):
#         self.tokens: list[Item] = list_of_tokens
#         self.metadata: dict[str, str | int] = {}
#         self.buffer: list[str] = []

#     def construct_metadata(self) -> dict[str, str | int]:
#         capture_title = False
#         title_parts = []
#         i = 0
#         while i < len(self.tokens):
#             item = self.tokens[i]

#             if item.typ == ItemType.Text and not capture_title:
#                 self.buffer.append(item.val)

#             elif item.typ == ItemType.CollectionType:
#                 self.metadata["collection_type"] = item.val

#             elif item.typ == ItemType.IssueNumber:
#                 try:
#                     self.metadata["issue"] = int(item.val.lstrip("#"))
#                     capture_title = True
#                 except ValueError:
#                     pass

#             elif item.typ == ItemType.VolumeNumber:
#                 volume = int(re.findall(r"\d+", item.val)[0])
#                 self.metadata["volume"] = volume
#                 capture_title = True

#             elif capture_title:
#                 if item.typ == ItemType.Text:
#                     title_parts.append(item.val)
#                 elif item.typ == ItemType.Number:
#                     if 1900 <= int(item.val):
#                         self.metadata["year"] = int(item.val)
#                         break

#             elif item.typ == ItemType.Number and 1900 <= int(item.val):
#                 self.metadata["year"] = int(item.val)
#                 break

#             i += 1

#         if self.buffer:
#             tokens = " ".join(self.buffer).split()
#             self.metadata["series"] = " ".join(tokens)

#         if title_parts:
#             title = " ".join(title_parts).strip().lstrip("-").strip()
#             if title:
#                 self.metadata["title"] = " ".join(title.split())

#         return self.metadata

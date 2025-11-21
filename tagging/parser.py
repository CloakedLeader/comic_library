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
        self.item_length = len(tokens)
        self.includes_dash = False
        for i in tokens:
            if i.typ == LexerType.Dash:
                self.includes_dash = True
                break
            else:
                continue
        

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
        self.pos += n
        token = self.current()
        return token
    
    def skip_whitespaces(self) -> int:
        n = 1
        while True:
            next_typ = self.peek(n=n).typ
            if next_typ == LexerType.Space:
                n += 1
                continue
            else:
                break
        return n
    
    def try_parse_date_in_paren(self) -> Optional[int]:
        if self.peek().typ == LexerType.EOF:
            return None
        maybe_year = self.peek()
        if maybe_year.typ == LexerType.Number or len(maybe_year.val) == 4:
            if self.peek(2).typ == LexerType.RightParen:
                year_tok = int(maybe_year.val)
                if year_tok > 1900:
                    self.next(); self.next()
                    return year_tok
        return None
    
    def try_parse_useless_info(self, seen_year_yet: bool) -> Optional[str]:
        if self.peek().typ == LexerType.EOF:
            return None
        maybe_useless = self.peek()
        if maybe_useless.typ == LexerType.Text and seen_year_yet:
            if self.pos + 1 >= self.item_length - 3:
                useless_tok = str(maybe_useless.val)
                self.next()
                return useless_tok
        
        return None
    
    def try_parse_issue_number(self) -> Optional[int]:
        if self.peek().typ == LexerType.EOF:
            return None
        n = self.skip_whitespaces()
        maybe_num = self.peek(n=n)
        if maybe_num.typ == LexerType.Number:
            number_tok = maybe_num.val
            self.next(n=n)
            return int(number_tok)
        else:
            return None
        
    def try_parse_volume_number(self) -> Optional[int]:
        if self.peek().typ == LexerType.EOF:
            return None
        n = self.skip_whitespaces()
        maybe_num = self.peek(n=n)
        if maybe_num.typ == LexerType.Number:
            number_tok = int(maybe_num.val)
            self.next(n=n)
            if number_tok < 12:
                return int(number_tok)
        return None
    
    def decide_if_seperator(self) -> bool:
        if self.prev().typ == LexerType.Space and self.peek() == LexerType.Space:
            return True
        else:
            return False

    def parse(self):
        
        title_parts: list[str] = []
        series_parts: list[str] = []
        useless_info: list[str] = []

        dash_yet: bool = False
        year_yet: bool = False

        while True:
            tok = self.current()

            if tok.typ == LexerType.EOF:
                break

            if tok.typ == LexerType.LeftParen:
                maybe_date = self.try_parse_date_in_paren()
                if maybe_date:
                    metadata_year = maybe_date
                    year_yet = True
                    continue
                else:
                    maybe_useless = self.try_parse_useless_info(year_yet)
                    if maybe_useless:
                        useless_info.append(maybe_useless)
                    title_parts.append(tok.val)
                    self.next()
                    continue

            if tok.typ == LexerType.Symbol and tok.val == "#":
                maybe_issue_num = self.try_parse_issue_number()
                if maybe_issue_num:
                    metadata_issue_num = maybe_issue_num
                    continue
                else:
                    self.next()
                    continue

            if tok.typ == LexerType.Text:
                val = tok.val.lower()
                if val.rstrip(".") in ("vol", "volume", "v"):
                    maybe_volume_num = self.try_parse_volume_number()
                    if maybe_volume_num:
                        metadata_volume_num = maybe_volume_num
                        continue
                elif val == "by":
                    maybe_author = self.try_parse_author()
                    if maybe_author:
                        metadata_author = maybe_author
                        continue
                else:
                    if dash_yet:
                        title_parts.append(val)
                        self.next()
                        continue
                    else:
                        series_parts.append(val)
                        self.next()
                        continue

            if tok.typ == LexerType.Dash:
                dash_yet = self.decide_if_seperator()
                self.next()
                continue


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

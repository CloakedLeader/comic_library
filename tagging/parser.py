import re
from dataclasses import dataclass
from typing import Optional

from .itemtypes import Item, LexerType


@dataclass
class FilenameMetadata:
    title: str
    volume_number: int
    series: str
    issue_number: Optional[int]
    collection_type: Optional[str]
    year: int
    # month: Optional[int]

    def __str__(self) -> str:
        return f"""
            Series: {self.series}
            Title: {self.title}
            Volume: {self.volume_number}
            Issue: {self.issue_number}
            Year: {self.year}
            Collection Type: {self.collection_type or "None"}
        """

    def __repr__(self) -> str:
        return f"""
            Series: {self.series}
            Title: {self.title}
            Volume: {self.volume_number}
            Issue: {self.issue_number}
            Year: {self.year}
            Collection Type: {self.collection_type or "None"}
        """


known_collections = {
    "tpb",
    "hc",
    "hardcover",
    "omnibus",
    "deluxe",
    "compendium",
    "digest",
}


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
        if maybe_year.typ == LexerType.Number and len(maybe_year.val) == 4:
            if self.peek(2).typ == LexerType.RightParen:
                year_tok = int(maybe_year.val)
                if year_tok > 1900:
                    self.next()
                    self.next()
                    return year_tok
        return None

    def try_parse_useless_info(self, seen_year_yet: bool) -> Optional[str]:
        if self.peek().typ == LexerType.EOF:
            return None
        maybe_useless = self.peek()
        if maybe_useless.typ == LexerType.Text and seen_year_yet:
            if self.pos + 1 >= self.item_length - 4:
                useless_tok = str(maybe_useless.val)
                self.next()
                return useless_tok

        return None

    def skip_parenthesis(self):
        depth = 0

        while True:
            tok = self.current()
            if tok.typ == LexerType.EOF:
                break
            if tok.typ == LexerType.LeftParen:
                depth += 1
            elif tok.typ == LexerType.RightParen:
                depth -= 1
                if depth == 0:
                    self.next()
                    break
                else:
                    self.next()
                    continue
            self.next()

    def try_parse_issue_number(self, hash: bool) -> Optional[int]:
        if hash:
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
        else:
            maybe_num = self.current()
            if maybe_num.typ == LexerType.Number:
                number_tok = maybe_num.val
                self.next()
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

    def decide_if_separator(self) -> bool:
        if self.prev().typ == LexerType.Space and self.peek().typ == LexerType.Space:
            return True
        else:
            return False

    def try_parse_author(self):
        pass

    def count_dashes(self) -> int:
        count = 0
        for token in self.tokens:
            if token.typ == LexerType.Dash:
                count += 1

        return count

    def parse(self) -> FilenameMetadata:
        title_parts = []
        series_parts = []
        possible_metadata: dict[str, str | int] = {
            "year": 0,
            "issue": 0,
            "volume": 0,
            "collection": "",
            "author": "",
        }

        dashes = self.count_dashes()
        dash_count = 0

        while True:
            tok = self.current()

            if tok.typ == LexerType.EOF:
                break

            elif tok.typ == LexerType.Space:
                self.next()

            elif tok.typ == LexerType.LeftParen:
                maybe_date = self.try_parse_date_in_paren()
                if maybe_date:
                    possible_metadata["year"] = maybe_date
                    continue
                else:
                    self.skip_parenthesis()
                    continue

            elif tok.typ == LexerType.Symbol and tok.val == "#":
                maybe_issue_num = self.try_parse_issue_number(True)
                if maybe_issue_num:
                    possible_metadata["issue"] = maybe_issue_num
                    continue
                else:
                    self.next()
                    continue

            elif tok.typ == LexerType.Number:
                if possible_metadata["issue"] == 0:
                    maybe_iss_num = self.try_parse_issue_number(False)
                    if maybe_iss_num:
                        possible_metadata["issue"] = maybe_iss_num
                        continue
                    else:
                        self.next()
                        continue
                else:
                    self.next()
                    continue

            elif tok.typ == LexerType.Text:
                val = tok.val.lower()
                if val[0] == "v":
                    m = re.match(r"^(v(?:ol(?:ume)?)?)\.?(\d+)$", val.rstrip("."))
                    if m:
                        maybe_volume_num = int(m.group(2))
                        if maybe_volume_num:
                            possible_metadata["volume"] = maybe_volume_num
                            self.next()
                            continue
                    elif not val[-1].isdigit() and val in ("v", "vol", "volume"):
                        maybe_volume_num = self.try_parse_volume_number()  # type: ignore
                        if maybe_volume_num:
                            possible_metadata["volume"] = maybe_volume_num
                            continue
                elif val in known_collections:
                    possible_metadata["collection"] = val
                    self.next()
                    continue
                elif val == "by":
                    maybe_author = self.try_parse_author()
                    if maybe_author:
                        possible_metadata["author"] = maybe_author
                        continue
                else:
                    if dashes > 0:
                        if dash_count >= dashes:
                            title_parts.append(val)
                            self.next()
                            continue
                        else:
                            series_parts.append(val)
                            self.next()
                            continue
                    else:
                        title_parts.append(val)
                        self.next()
                        continue

            elif tok.typ == LexerType.Dash:
                dash_count += 1
                self.next()
                continue

            else:
                self.next()

        for i in ["issue", "volume"]:
            if possible_metadata[i] == 0:
                possible_metadata[i] = 1

        return FilenameMetadata(
            title=" ".join(title_parts),
            series=" ".join(series_parts),
            volume_number=int(possible_metadata["volume"] or 1),
            issue_number=int(possible_metadata["issue"] or 1),
            collection_type=str(possible_metadata["collection"]),
            year=int(possible_metadata["year"]),
        )

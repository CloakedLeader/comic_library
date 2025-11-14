import os
import re
from dotenv import load_dotenv
from itemtypes import ItemType, Item


load_dotenv()
API_KEY = os.getenv("API_KEY")


class Parser:
    def __init__(self, list_of_tokens: list[Item]):
        self.tokens: list[Item] = list_of_tokens
        self.metadata: dict[str, str | int] = {}
        self.buffer: list[str] = []

    def construct_metadata(self) -> dict[str, str | int]:
        capture_title = False
        title_parts = []
        i = 0
        while i < len(self.tokens):
            item = self.tokens[i]

            if item.typ == ItemType.Text and not capture_title:
                self.buffer.append(item.val)

            elif item.typ == ItemType.CollectionType:
                self.metadata["collection_type"] = item.val

            elif item.typ == ItemType.IssueNumber:
                try:
                    self.metadata["issue"] = int(item.val.lstrip("#"))
                    capture_title = True
                except ValueError:
                    pass

            elif item.typ == ItemType.VolumeNumber:
                volume = int(re.findall(r"\d+", item.val)[0])
                self.metadata["volume"] = volume
                capture_title = True

            elif capture_title:
                if item.typ == ItemType.Text:
                    title_parts.append(item.val)
                elif item.typ == ItemType.Number:
                    if 1900 <= int(item.val):
                        self.metadata["year"] = int(item.val)
                        break

            elif item.typ == ItemType.Number and 1900 <= int(item.val):
                self.metadata["year"] = int(item.val)
                break

            i += 1

        if self.buffer:
            tokens = " ".join(self.buffer).split()
            self.metadata["series"] = " ".join(tokens)

        if title_parts:
            title = " ".join(title_parts).strip().lstrip("-").strip()
            if title:
                self.metadata["title"] = " ".join(title.split())

        return self.metadata
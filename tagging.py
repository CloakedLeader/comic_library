import calendar
import os
import re
from enum import Enum, auto
from typing import Callable, Protocol
import xml.etree.ElementTree as ET


start_time = time.time()

load_dotenv()

# ==================================
#   Filename Lexing
# ==================================

def is_numeric_or_number_punctuation(x: str) -> bool:
    digits = "0123456789.,"
    return x.isnumeric() or x in digits



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
    

class Item:
    
    def __init__( self, typ: ItemType, pos: int, val: str ) -> None:
        """
        Creates a new item which has been found in the string.

        Parameters:
        typ [ItemType] = The type defined above e.g. text or parenthesis.
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
    
    def __call__( self, __origin: 'Lexer') -> 'LexerFunc | None': ... # type: ignore
    



class Lexer:
    
    def __init__( self, string: str, *, allow_issue_start_with_letter: bool = False) -> None:
        self.input: str = string
        self.state: LexerFunc | None = None
        self.pos: int = -1
        self.start: int = 0
        self.last_pos: int = 0
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
        return self.input[ self.pos ]
    
        
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
    
    def match(self, s: str) -> bool:
        """
        If the upcoming characters match the given string 's', consume them and return True.
        Otherwise, leave input untouched and return False.
        """
        end = self.pos + len(s)
        if self.input[self.pos:end].lower() == s.lower():
            self.pos = end
            return True
        return False
    
    def match_any(self, options: list[str]) -> str | None:
        """
        Tries to match any of the strings in 'options'. Returns the matched string if successful, else None.
        """
        for s in options:
            if self.match(s):
                return s
        return None
    
    def scan_number( self ) -> bool:
        """
        Checks if a string is numeric and if it has a suffix of letters directly after, no whitespace.
        """
        if not self.accept_run(is_numeric_or_number_punctuation):
            return False
        if self.input[self.pos] == ".":
            self.backup()
        self.accept_run(str.isalpha)
        return True
    
    def run(self) -> None:
        # Keeps the lexer process running
        self.state = run_lexer
        while self.state is not None:
            self.state = self.state(self)

def errorf(lex: Lexer, message: str) -> None:
    lex.items.append(Item(ItemType.Error, lex.start, message))

def run_lexer( lex: Lexer) -> LexerFunc:
    r = lex.get()

    if r == eof:
        lex.emit(ItemType.EOF)
        return None
    
    elif r.isspace():
        lex.ignore()
        return run_lexer

    elif r.isnumeric():
        lex.backup()
        return lex_number
    
    elif r == "#":
        if lex.peek().isnumeric():
            return lex_issue_number
        else:
            return errorf(lex, "expected number after #")
        
    elif r.lower() == "v":
        if lex.peek().isdigit():
            return lex_volume_number
        elif lex.match("ol.") or lex.match("ol") or lex.match("olume"):
            return lex_volume_number_full
        return lex_text

    elif r.lower() == "b":
        lex.backup()
        if lex.match("by "):
            lex.emit(ItemType.InfoSpecifier)
            return lex_author  
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
        return errorf(lex, f"unexpected character: {r}")

def lex_space(lex: Lexer) -> LexerFunc:
    if lex.accept_run(is_space):
        lex.emit(ItemType.Space)
    return run_lexer
    

def lex_text(lex: Lexer) -> LexerFunc:
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
    

            
def lex_number(lex: Lexer) -> LexerFunc | None:
    # Attempt to scan number from current position
    if not lex.scan_number():
        return errorf(lex, "bad number syntax: " + lex.input[lex.start : lex.pos])

    # Handle ordinal or letter suffixes (e.g. '80th' or '20s')
    if lex.pos < len(lex.input) and lex.input[lex.pos].isalpha():
        lex.accept_run(str.isalpha)
        lex.emit(ItemType.Text)
        return run_lexer
    lex.emit(ItemType.Number)
    return run_lexer


def lex_issue_number(lex: Lexer) -> LexerFunc:
    # Only called when lex.input[lex.start] == "#"
    if not lex.peek().isnumeric():
        lex.emit(ItemType.Symbol)
        return run_lexer
    
    lex.accept_run(str.isdigit)

    lex.accept_run(str.isalpha)

    lex.emit(ItemType.IssueNumber)
    return run_lexer

def lex_author(lex: Lexer) -> LexerFunc:
    lex.accept_run(str.isspace)
    name_parts = 0

    while name_parts < 3:
        word_start = lex.pos
        lex.accept_run(str.isalpha)

        word = lex.input[word_start:lex.pos]

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
    
    if name_parts >= 2:
        lex.emit(ItemType.Author)
    else:
        lex.emit(ItemType.Text)

    return run_lexer

# def lex_author(lex: Lexer) -> LexerFunc:
#     # Consume one or more words (allowing initials)
#     while True:
#         lex.accept_run(str.isalpha)  # e.g., "Brian"
#         if lex.accept(" "):
#             peek = lex.peek()
#             if peek.isalpha() or peek == ".":  # Accept middle initials or next name
#                 continue
#             else:
#                 break
#         else:
#             break

#     lex.emit(ItemType.Author)
#     return run_lexer  # resume normal lexing


def  lex_collection_type(lex: Lexer) -> LexerFunc:
    lex.accept_run(str.isalpha)
    word = lex.input[lex.start:lex.pos].casefold()

    known_collections = {
        "tpb", "hc", "hardcover", "omnibus", "deluxe", "compendium", "digest"
    }

    if word in known_collections:
        lex.emit(ItemType.CollectionType)
    else:
        lex.emit(ItemType.Text)

    return run_lexer

def lex_volume_number(lex: Lexer) -> LexerFunc:
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
    lex.accept_run(str.isdigit)

    if lex.pos > lex.start:
        lex.emit(ItemType.VolumeNumber)
    else:
        lex.emit(ItemType.Text)

    return run_lexer

def is_space(character: str) -> bool:
    return character.isspace() or character == "_"

def is_alpha_numeric(character: str) -> bool:
    return character.isalpha() or character.isnumeric()

def cal(word: str) -> bool:
    word_lower = word.lower()

    months = [m.lower() for m in calendar.month_name if m] + [m.lower() for m in calendar.month_abbr if m]
    if word_lower in months:
        return True

    return bool(re.fullmatch(r"\d{4}", word) or re.fullmatch(r"\d{4}s", word))

def lex(filename: str, allow_issue_start_with_letter: bool = False) -> Lexer:
    lex = Lexer(os.path.basename(filename), allow_issue_start_with_letter)
    lex.run()
    return lex

def sort_imgs(filename: str) -> Optional[int]:
    numbers = re.findall(r'\d+', filename)
    return int(numbers[-1]) if numbers else -1

class RequestData:
    
    def __init__( self, name: str, issue_num: int, year: int, series: str, title: str, publisher: str = None ):
        self.series = series
        self.title = title
        self.unclean_title = name
        self.num = issue_num
        self.pub_year = year
        self.publisher = publisher
    
header = {
    "User-Agent": "AutoComicLibrary/1.0 (contact: adam.perrott@protonmail.com; github.com/CloakedLeader/comic_library)",
    "Accept": r"*/*",
    "Accept-Encoding": "gzip,deflate,br",
    "Connection": "keep-alive"
}
session = requests.Session()
session.headers.update(header)

class HttpRequest:

    base_address = f"https://comicvine.gamespot.com/api"
    
    def __init__( self, data: RequestData ):
        self.data = data
        self.payload = self.create_info_dict()

    def create_info_dict( self ):
        payload = {}
        payload["api_key"] = api_key
        payload["resources"] = "volume"
        payload["field_list"] = "id,image,publisher,name,start_year,date_added,count_of_issues,description,last_issue"
        payload["format"] = "json"
        payload["query"] = self.data.unclean_title
        payload["limit"] = 50
        return payload

    def build_url_search( self ):
        req = requests.Request(
            method="GET",
            url=f"{HttpRequest.base_address}/search/",
            params=self.payload,
            headers=header
        )
        prepared = req.prepare()
        self.url_search = prepared.url
        print(self.url_search)

    def build_url_iss( self, id: int ):
        req = requests.Request(
            method="GET",
            url=f"{HttpRequest.base_address}/issues/",
            params={
                "api_key" : api_key,
                "format" : "json",
                "filter" : f"volume:{id}"
            }
        )
        prepared = req.prepare()
        self.url_iss = prepared.url
        print(self.url_iss)
    
    def get_request( self, type: str ):
        if type == "search": 
            if not hasattr(self, "url_search"):
                raise RuntimeError("You must build url before sending request.")
            response = session.get(self.url_search)
            if response.status_code != 200:
                print(f"Request failed with status code: {response.status_code}")
                print(response.text)
            data = response.json()

        elif type == "iss":
            if not hasattr(self, "url_iss"):
                raise RuntimeError("You must build url before sending request.")
            response = session.get(self.url_iss)
            if response.status_code != 200:
                print(f"Request failed with status code: {response.status_code}")
                print(response.text)
            data = response.json()

        else:
            print("Need to specify which database to search in.")
        if data["error"] != "OK":
                print("Error, please investigate")
                return
        # Want to tell the user to manually tag the comic.
        return data
    
    def download_img( self, url ):
        try:
            response = requests.get(url)
            response.raise_for_status()
            image = (BytesIO(response.content))
            return image
        except Exception as e:
            print(f"Failed to process {url}: {e}")
            return None

class ResponseValidator:

    issue_threshold = 80
    volume_threshold = 60

    def __init__( self, response: dict, expected_data: RequestData ):
        self.results = response["results"]
        self.expected_info = expected_data

    def filter_results( self, predicate):
        return [item for item in self.results if predicate(item)]

    def year_checker( self ):
        def check_year(item):
            year = int(item["date_added"][:4])
            return abs( year - self.expected_info.pub_year ) <= 3
        return self.filter_results(check_year)
    
    @staticmethod
    def fuzzy_match( a, b, threshold=65 ):
        return fuzz.token_sort_ratio( a, b ) >= threshold

    def title_checker( self ):
        def check_title(item):
            used_fallback = False
            ambig_names = ["tpb", "hc", "omnibus"]
            ambig_regexes = [
                r"^vol(?:ume)?\.?\s*\d+$", # matches "vol. 1", "volume 2", "vol 3"
                r"^#\d+$", # matches "#1", "#12" etc
                r"^issue\s*\d+$", # matches "issue 3"
                r"\bvol(?:ume)?\.?\s*(one|two|three|four|\d+|i{1,3}|iv|v)\b"
            ]
            title = item["name"]
            if title:
                lowered_title = title.lower().strip()
                is_ambig = (
                    lowered_title in ambig_names or 
                    any(re.match(p, lowered_title) for p in ambig_regexes) 
                )
                if is_ambig:
                    title = item.get("volume", {}).get("name")
                    used_fallback = True
            else:
                title = item.get("volume", {}).get("name")
                used_fallback = True
            if title is None:
                return False
            threshold = ResponseValidator.volume_threshold if used_fallback else ResponseValidator.issue_threshold
            return self.fuzzy_match(title, self.expected_info.unclean_title, threshold=threshold)
        return self.filter_results(check_title)

    def vol_title_checker( self ):
        def check_title(item):
            title = item["name"]
    
    def pub_checker( self, results: list ):
        foriegn_keywords = {"panini", "verlag", "norma", "televisa", "planeta", "deagostini", "urban"}
        english_publishers = {
            "Marvel": 31,
            "DC Comics": 10,
            "Image": 513,
            "IDW Publishing": 1190,
            "Dark Horse Comics": 364 
            }
        
        filtered = []
        for result in results:
            pub_dict = result["publisher"]
            pub_id = pub_dict["id"]
            pub_name = pub_dict["name"]
            if pub_id in english_publishers.values():
                filtered.append(result)
            elif any(word.lower() in foriegn_keywords for word in pub_name.split()):
                print(f"Filtered out {pub_name} due to foreign publisher.")
            else:
                filtered.append(result)
                print(f"Accepted '{pub_name}' but please check to see if they need adding to foriegn publishers.")
        return filtered

    def issue_count_filter( self, limit: int = 12 ):
        def is_collection(item):
            issue_count = item["count_of_issues"]
            return True if issue_count < limit else False
        return self.filter_results(is_collection)
    
    def cover_img_url_getter( self, filtered_results ):
        self.urls = []
        for i in filtered_results:
            self.urls.append(i["image"]["thumb_url"])

    def cover_img_comparison( self, known_image_hash, unsure_image_bytes, threshold=8) -> bool: # Returns true if it finds match.
        unsure_image = Image.open(unsure_image_bytes)
        hash1 = known_image_hash
        hash2 = imagehash.phash(unsure_image)
        hash_diff = hash1 - hash2
        print(f"[DEBUG] Hashing distance = {hash_diff}, threshold = {threshold}")
        return hash_diff <= threshold
    
    def cover_img_comp_w_weight( self, known_image_hashes, unsure_image_bytes, max_dist=64):
        weights = {
            "phash" : 0.6,
            "dhash" : 0.2,
            "ahash" : 0.2
        }
        unsure_hashes = {
            "phash" : imagehash.phash(unsure_image_bytes),
            "dhash" : imagehash.dhash(unsure_image_bytes),
            "ahash" : imagehash.average_hash(unsure_image_bytes)
        }
        score = 0.0
        for key in weights:
            dist = known_image_hashes[key] - unsure_hashes[key]
            normalised = 1 - (dist / max_dist)
            score += weights[key] * normalised
        return score

class TaggingPipeline:
    def __init__( self, data: RequestData, path: str, size: float ):
        self.data = data
        self.path = path
        self.size = size
        self.http = HttpRequest(data)
        self.validator = None
        self.cover = self.cover_getter()
        self.coverhashes = self.cover_hasher() # dictionary of (phash, dhash, ahash)

    def cover_getter( self ):
        with zipfile.ZipFile(self.path, 'r') as zip_ref:
            image_files = [f for f in zip_ref.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            if not image_files:
                print("Empty archive.")
                return
            image_files.sort()
            cover = zip_ref.read(image_files[0])
            deb = Image.open(BytesIO(cover))
            deb.show()
            return BytesIO(cover)
    
    def cover_hasher( self ):
        image = Image.open(self.cover)
        return {
            "phash" : imagehash.phash(image),
            "dhash" : imagehash.dhash(image),
            "ahash" : imagehash.average_hash(image)
        }

        
    def ask_user(self, results: list):
        pass
    

    def run( self ):
        self.http.build_url_search()
        results = self.http.get_request("search")
        self.validator = ResponseValidator( results, self.data )

        print(f"There are {len(results["results"])} results returned from HTTP query.")
        results = self.validator.issue_count_filter()
        self.validator.results = results
        results = self.validator.title_checker()
        self.validator.results = results
        results = self.validator.pub_checker(results)
        self.validator.results = results
        print(f"After filtering for title, publisher and issue count, there are {len(results)} remaining matching volumes.")
        final_results = results

        if len(final_results) == 0:
            # No results - need to come up with logic/a solution here.
            pass
        
        print(f"There are {len(final_results)} volumes to check")
        vol_info = []
        for i in final_results:
            id = i["id"]
            name = i["name"]
            vol_info.append((id, name))
        good_matches = []
        skipped_vols = []
        for j, k in vol_info:
            self.http.build_url_iss(j)
            temp_results = self.http.get_request("iss")

            self.temp_validator = ResponseValidator( temp_results, self.data )
            print(f"There are {len(self.temp_validator.results)} issues in the matching volume: '{k}'.")
            temp_results = self.temp_validator.year_checker()
            self.temp_validator.results = temp_results
            temp_results = self.temp_validator.title_checker()
            self.temp_validator.results = temp_results

            print(f"After filtering for title and year there are {len(temp_results)} results remaining.")
            if len(temp_results) != 0:
                if len(temp_results) > 25:
                    print(f"Too many issues to compare covers, skipping volume '{k}'.")
                    skipped_vols.append((j, k, len(temp_results)))
                    continue
                self.temp_validator.cover_img_url_getter(temp_results)
                images =[]
                with ThreadPoolExecutor(max_workers=5) as executor:
                    images = list(executor.map(self.http.download_img, self.temp_validator.urls))
                matches_indices = []
                for index, i in enumerate(images):
                    if i is None:
                        continue
                    try:
                        img_pil = Image.open(i)
                        score = self.temp_validator.cover_img_comp_w_weight(self.coverhashes, img_pil)
                        print(f"Index {index}: similarity score = {score:.2f}")
                        if score > 0.85:
                            matches_indices.append(index)
                    except Exception as e:
                        print(f"Error comparing image at index {index}: {e}.")
                final_results = [temp_results[i] for i in matches_indices]
                good_matches.extend(final_results)
            else:
                continue

        if len(good_matches) == 1:
            print(good_matches[0]["volume"]["name"])
            print("There is ONE match!!!")
            return good_matches
        elif len(good_matches) == 0:
            print("There are no matches.")
            #If there is no matches need to do something. Perhaps the comic is new and hasnt been uploaded onto comicvine properly.
        elif len(good_matches) > 1:
            for i in good_matches:
                print(i["volume"]["name"])
            print(f"FINAL COUNT: There are {len(good_matches)} remaining matches.")    
            #Need to use scoring or sorting or closest title match etc.
            #If that cant decide then we need to flag the comic and ask the user for input.

for i in range(1000000):
    pass
end_time = time.time()
print(f"Execution time: {end_time - start_time:.4f} seconds")

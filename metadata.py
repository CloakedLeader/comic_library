import os
import zipfile
import xml.etree.ElementTree as ET
import sqlite3
from typing import Optional, Union, Tuple, List
from fuzzywuzzy import fuzz
import sys
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import re
from word2number import w2n




log_file = open("log.txt", "w")
sys.stout = log_file


def find_cover(path): #This needs to be completely changed later. 
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path, 'r') as zip_ref:
            image_files = [f for f in zip_ref.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            if not image_files:
                print("Empty archive.")
                return
    else:
        print("Need to convert to cbz first!")

    image_files.sort()
    first_image = zip_ref.read(image_files[0])
    return first_image


def find_metadata(path: str) -> ET.Element:
    try:
            with zipfile.ZipFile(path, 'r') as cbz:
                cbz.getinfo('ComicInfo.xml')
                with cbz.open('ComicInfo.xml') as xml_file:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    return (root, None) 
    except zipfile.BadZipFile:
        return (None, "Not a valid CBZ/ZIP file.")
    except FileNotFoundError:
        return (None, "File not found.")
    except Exception as e:
        return(None, f"Unexpected error: {e}" )
    
                      

def get_text(root, tag: str) -> Optional[str]:
    element = root.find(tag)
    if element is not None and element.text:
        return element.text.strip().lower()
    else:
        print("No metadata under {tag} tag.")


def normalise_publisher(name: str) -> Optional[str]:
    suffixes = ["comics", "publishing", "group", "press", "inc.", "inc", "llc"]
    tokens = name.replace("&", "and").split()
    return " ".join([t for t in tokens if t not in suffixes])


# Parsing the easy metadata which requires no logic

def easy_parse(path: str, field:str, as_type: type = str ) -> Union[str, int, None]: #Add messages to catch errors when this function returns None
    root, error = find_metadata(path)
    if error:
        print("Error reading metadata:", error)
    elif root is not None:
        text = get_text(root, field)
        if text is None:
            return None
        try:
            return as_type(text)
        except ValueError:
            print(f"Could not convert {field} to {as_type.__name__}")
            return None
    else:
        print("No ComicInfo.xml found")
        return None


def parse_desc(path) -> Optional[str]:
    return easy_parse(path, "Summary")

def parse_series(path) -> Optional[str]:
    return easy_parse(path, "Series")

def parse_vol_num(path) -> Optional[int]:
    return easy_parse(path, "Number", int)

def parse_year(path) -> Optional[int]:
    return easy_parse(path, "Year", int)

def parse_month(path) -> Optional[int]:
    return easy_parse(path, "Month", int)
    
def parse_publisher(path) -> Optional[str]:
    return easy_parse(path, "Publisher")

def parse_title(path) -> Optional[str]:
    return easy_parse(path, "Title")

def parse_creator(path, tag: str) -> Optional[List[str]]: #Returns a list of strings where each string is an indivdual name 
    creators = easy_parse(path, tag)
    return creators.split(", ")




# More advanced parsing that requires extra logic or string matching

def match_publisher(a: str) -> Optional[int]:  # Takes a string from metadata and returns the publisher id that comes from sql publisher table primary key
    known_publishers = [(1,"Marvel Comics"), (2, "DC Comics"), (3, "Image Comics"), (4, "Dark Horse Comics"), (5, "IDW Comics"), (6,"Valiant Comics"), (7, "2000AD Comics")]
    best_score = 0
    best_match = None
    for pub_id, pub_name in known_publishers:
        score = fuzz.token_set_ratio(normalise_publisher(a), normalise_publisher(pub_name))
        if score > best_score:
            best_score = score
            best_match = (pub_id, pub_name)
    if best_score >= 85:
        return best_match[0]
    else:
        None

#use Amazing Spider-Man Modern Era Epic Collection: Coming Home

# File Naming System: [Series_Name][Start_Year] - [Collection_Type] [Volume_Number] ([date in month/year])
# User Visible Title: [Series] [star_year] - [collection type] Volume [volume_number]: [Title] [month] [year]


series_overrides = [("tpb", 1), ("omnibus", 2), ("epic collection", 3), ("modern era epic collection", 4)]

def title_parsing(path) -> Optional[Tuple[str, int]]:
    common_titles = {'volume', 'book', 'collection'}
    coll_type = None
    override = False
    title_raw = parse_title(path)
    match = re.search(r'volume\s(\d+)|(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen)', title_raw)

    if match:
        title = parse_series(path)
        vol = match.group(1)
        if vol.isdigit():
            vol_num = int(vol)
        else:
            vol_num = w2n.word_to_num(vol) #need to deal with vol_num being None
#need to deal with 'volume being in the title but other stuff around it' 
    for f in series_overrides:      
        if f[0] in title:
            title = title.replace(f[0], "")
            override = True
            coll_type = f[1]
        if coll_type is None:
            pass #Need to add a function which will defintely find the type of collection
        elif override == False:
            print("No usuable title, need user input.") #Need to do something here to fix if no title can be found


def build_dict(path) -> Optional[dict]:
    dic = dict.fromkeys(["title", "series", "volume_id", "publisher_id", "release_date", "file_path", "front_cover_path", "description"])
    dic["description"] = parse_desc(path)
    dic["file_path"] = f"{path}"
    dic["publisher_id"] = match_publisher(parse_publisher(path))
    dic["release_date"] = f"{parse_month(path)}/{parse_year(path)}"
    return dic

def dic_into_db(my_dic) -> None:
    conn = sqlite3.connect("comics.db")
    cursor = conn.cursor()
    # ready_or_not = True
    for value in my_dic:
        if value is None:
            print("Missing some information") #Need to trigger another function or re-tag to get appropriate data
        else:
            cursor.execute('''
                   INSERT INTO comics (title, series, volume_id, publisher_id, release_date, file_path, front_cover_path, description)
                   VALUES (:title, :series, :volume_id, :pubslisher_id, :release_date, :file_path, :front_cover_path, :description)
                   ''', my_dic)
    conn.commit()
    conn.close()

                                         


# Watchdog stuff:

path_to_obs = os.getenv("PATH_TO_WATCH")

class DownloadsHandler(FileSystemEventHandler):

    def on_created(self, event):
        if not event.is_directory:
            file_path = event.src_path
            print(f"New file detected: {file_path}")
            self.handle_new_file(file_path)
            
    def on_moved(self, event):
        if event.dest_path == path_to_obs:
            if not event.is_directory:
                file_path = event.src_path
                print(f"New file detected: {file_path}")
                self.handle_new_file(file_path)
        else:
            pass
    
    def on_modified(self, event): #Need to do something here
        pass

    def on_deleted(self, event):
        print(f"Detected a file deletion: {event.src_path}")

    def handle_new_file(self, path): #Start the tagging
        pass


obs = Observer()
obs.schedule(DownloadsHandler(), path_to_obs, recursive = False)
obs.start()
try: 
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    obs.stop()
    obs.join()

    





import os
import zipfile
import xml.etree.ElementTree as ET
import sqlite3
from typing import Optional, Union
from fuzzywuzzy import fuzz
import sys
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


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
    return element.text.strip() if element is not None and element.text else None


def normalise_publisher(name: str) -> Optional[str]:
    suffixes = ["comics", "publishing", "group", "press", "inc.", "inc", "llc"]
    tokens = name.lower().replace("&", "and").split()
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



def title_parsing(path):
    vague_titles = {'volume 1', 'volume one', 'book one', 'collection', 'tpb', 'omnibus'}



# Watchdog stuff:

class DownloadsHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            file_path = event.src_path
            print(f"New file detected: {file_path}")
            self.handle_new_file(file_path)

    

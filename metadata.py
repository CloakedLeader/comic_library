import os
import zipfile
import xml.etree.ElementTree as ET
import sqlite3
from typing import Optional
from fuzzywuzzy import fuzz




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


def find_metadata(path: str) -> ET.element:
    try:
            with zipfile.ZipFile(path, 'r') as cbz:
                cbz.getinfo('ComicInfo.xml')
                with cbz.open('ComicInfo.xml') as xml_file:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    return root
    except KeyError:
        return None
    except zipfile.BadZipFile:
        raise ValueError(f"File '{path}' is not a valid CBZ/ZIP file.")
                      

def get_text(root, tag: str) -> Optional[str]:
    element = root.find(tag)
    return element.text.strip() if element is not None and element.text else None


def normalise_publisher(name: str) -> Optional[str]:
    suffixes = ["comics", "publishing", "group", "press", "inc.", "inc", "llc"]
    tokens = name.lower().replace("&", "and").split()
    return " ".join([t for t in tokens if t not in suffixes])


# Parsing the easy metadata which requires no logic

def parse_desc(path) -> Optional[str]:
    root = find_metadata(path)
    return get_text(root, "Summary")

def parse_series(path) -> Optional[str]:
    root = find_metadata(path)
    return get_text(root, "Series")

def parse_year(path) -> Optional[int]:
    root = find_metadata(path)
    return int(get_text(root, "Year"))

def parse_month(path) -> Optional[int]:
    root = find_metadata(path)
    return int(get_text(root, "Month"))






def title_parsing(path):
    vague_titles = {'volume 1', 'volume one', 'book one', 'collection', 'tpb', 'omnibus'}
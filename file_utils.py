import os
import zipfile
import xml.etree.ElementTree as ET
import sqlite3

def convert_cbz():
    print("not done yet!")

def get_ext(path): #will eventually be used to intialise the cbz converter function
    return os.path.splittext(path)[1].lower()


def is_comic(): #extracts boolean for true or false, not sure this will be used
    return get_ext(path) in ('.cbz', '.cbr')


def parse_filename():
    print("not yet done!")


def move_file():
     print("not yet done!")


def find_metadata(path):
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


def easy_parsing(root): #Find a way to embed the find metadata function inside this one to avoid loads of nested functions
    def get_text(tag):
        element = root.find(tag)
        return element.text.strip() if element is not None and element.text else None
    return {
        "title": get_text("Title"),
        "series": get_text("Series"),
        "volume": get_text("Number"),
        #"publisher": get_text("Publisher"),
        #"year": get_text("Year"),
        #"month": get_text("Month"),
        "description": get_text("Summary")
    }

def add_easy(root):
    out = easy_parsing(root)
    with sqlite3.connect('comics.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
                INSERT INTO comics (title, series, volume_id, description)
                VALUES (:title, :series, :volume, :description)
                ''',
                out)
        
    



data = find_metadata('Juggernaut - No Stopping Now TPB (March 2021).cbz')
add_easy(data)         




def title_parsing(path):
    vague_titles = {'volume 1', 'volume one', 'book one', 'collection', 'tpb', 'omnibus'}
    
    

    



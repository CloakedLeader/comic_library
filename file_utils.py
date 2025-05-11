import os
import zipfile
import shutil
import tempfile
import rarfile
import xml.etree.ElementTree as ET
import sqlite3
from typing import Optional
from pathlib import Path

def convert_cbz(cbr_path, delete_original=False):
    if not get_ext(cbr_path) == ".cbr":
        raise ValueError("Not a .cbr file!")
    
    cbz_path = os.path.splitext(cbr_path)[0] + ".cbr"

    with tempfile.TemporaryDirectory() as tempdir:
        with rarfile.RarFile(cbr_path) as rf:
            rf.extractall(path=tempdir)
        
        with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(tempdir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, tempdir)
                    zf.write(full_path, rel_path)

    if delete_original:
        os.remove(cbr_path)
    
    print(f"Converted: {cbr_path} --> {cbz_path}")
    return cbz_path


    

def get_ext(path): #will eventually be used to intialise the cbz converter function
    return os.path.splitext(path)[1].lower()


def is_comic(path): #extracts boolean for true or false, not sure this will be used
    out = False
    if get_ext(path) in (".cbz, .cbr"):
        out = True
    return out

    

def move_file():
    pass

def get_name(path) -> str:
    return Path(path).stem



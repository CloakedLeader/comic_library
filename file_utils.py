import os
import zipfile
import xml.etree.ElementTree as ET
import sqlite3

def convert_cbz():
    pass

def get_ext(path): #will eventually be used to intialise the cbz converter function
    return os.path.splittext(path)[1].lower()


def is_comic(path): #extracts boolean for true or false, not sure this will be used
    return get_ext(path) in ('.cbz', '.cbr')


def parse_filename():
    pass


def move_file():
    pass


    



#('Juggernaut - No Stopping Now TPB (March 2021).cbz')
      

    

    



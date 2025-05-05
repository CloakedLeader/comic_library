import os
import zipfile

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


def find_metadata():
    print("not yet done!")

def find_cover(path): #Still needs a way to export to front end. Should be okay for now. 
    if zipfile.is_zipfile(path):
        with zipfile.Zipfile(path, 'r') as zip_ref:
            image_files = [f for f in zip_ref.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            if not image_files:
                print("Empty archive.")
                return
    else:
        print("Need to convert to cbz first!")

    image_files.sort()
    first_image = zip_ref.read(image_files[0])
    return first_image

    


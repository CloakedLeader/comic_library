import os
import tempfile
import uuid
import zipfile
from pathlib import Path

import rarfile


def convert_cbz(cbr_path: str, *, delete_original: bool = True) -> str:
    """
    Extracts files from a cbr archive and repackages them as a cbz.

    Args:
        cbr_path: The filepath of the cbr file/
        delete_original: The user has the choice of whether to
    delete the .cbr file or not.

    Returns:
        The filepath of the newly created .cbz file.

    Raises:
        ValueError: If the inputted filepath does not correspond
    to a .cbr file.

    Dumps the contents of the .cbr file to a temporary directory
    and then zips that directory into the .cbz with the same
    filename.
    """
    if not get_ext(cbr_path) == ".cbr":
        raise ValueError("Not a .cbr file!")

    cbz_path = os.path.splitext(cbr_path)[0] + ".cbz"

    with tempfile.TemporaryDirectory() as tempdir:
        with rarfile.RarFile(cbr_path) as rf:
            rf.extractall(path=tempdir)

        with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(tempdir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, tempdir)
                    zf.write(full_path, rel_path)

    if delete_original:
        os.remove(cbr_path)

    print(f"Converted: {cbr_path} --> {cbz_path}")
    return cbz_path


def get_ext(path: str) -> str:
    """
    Gets the file extension of specified file.
    """
    return os.path.splitext(path)[1].lower()


def is_comic(path: str) -> bool:
    """
    Tells whether a file is a comic archive or not.
    """
    comic_archives = [".cbz", ".cbr"]
    return get_ext(path) in comic_archives


def get_name(path: str) -> str:
    """
    Returns the filename of the specified filepath.
    """
    return Path(path).stem


def normalise_publisher_name(name: str) -> str:
    suffixes = ["comics", "publishing", "group", "press", "inc.", "inc", "llc"]
    tokens = name.replace("&", "and").lower().split()
    return " ".join([t for t in tokens if t not in suffixes])


def generate_uuid() -> str:
    return str(uuid.uuid4())

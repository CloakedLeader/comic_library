import os
import tempfile
import uuid
import zipfile
from pathlib import Path
import subprocess


def convert_cbz(cbr_path: str, *, delete_original: bool = True) -> str:
    """
    Extracts files from a cbr archive and repackages them as a cbz.

    Args:
        cbr_path: The filepath of the cbr file.
        delete_original: Whether to delete the .cbr file or not.

    Returns:
        The filepath of the newly created .cbz file.

    Raises:
        ValueError: If the inputted filepath does not correspond
    to a .cbr file.

    Dumps the contents of the .cbr file to a temporary directory
    and then zips that directory into the .cbz with the same
    filename.
    """
    cbr_path = Path(cbr_path)

    if not cbr_path.suffix.lower() == ".cbr":
        raise ValueError("Not a .cbr file!")

    if not cbr_path.exists():
        raise ValueError(f"File does not exist: {cbr_path}")

    cbz_path = cbr_path.with_suffix(".cbz")

    with tempfile.TemporaryDirectory() as tempdir:
        tempdir = Path(tempdir)
        result = subprocess.run(
            ["7z", "x", str(cbr_path), f"-o{tempdir}", "-y"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(
                f"7-Zip extraction failed for {cbr_path}:\n{result.stderr}"
            )

        with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in tempdir.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(tempdir))

    if delete_original:
        cbr_path.unlink()

    print(f"Converted: {cbr_path} --> {cbz_path}")
    return str(cbz_path)


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

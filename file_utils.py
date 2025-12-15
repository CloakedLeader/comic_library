import subprocess
import tempfile
import uuid
import zipfile
from pathlib import Path


def convert_cbz(cbr_path: Path, *, delete_original: bool = True) -> Path:
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

    if not cbr_path.suffix.lower() == ".cbr":
        raise ValueError("Not a .cbr file!")

    if not cbr_path.exists():
        raise ValueError(f"File does not exist: {str(cbr_path)}")

    cbz_path = cbr_path.with_suffix(".cbz")

    with tempfile.TemporaryDirectory() as tempdir:
        tempdir_ = Path(tempdir)
        result = subprocess.run(
            ["7z", "x", str(cbr_path), f"-o{tempdir_}", "-y"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"7-Zip extraction failed for {cbr_path.name}:\n{result.stderr}"
            )

        with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in tempdir_.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(tempdir))

    if delete_original:
        cbr_path.unlink()

    print(f"Converted: {cbr_path.name} --> {cbz_path.name}")
    return cbz_path


def is_comic(path: Path) -> bool:
    """
    Tells whether a file is a comic archive or not.
    """
    comic_archives = [".cbz", ".cbr"]
    return path.suffix.lower() in comic_archives


def get_name(path: Path) -> str:
    """
    Returns the filename of the specified filepath.
    """
    return path.stem


def normalise_publisher_name(name: str) -> str:
    suffixes = ["comics", "publishing", "group", "press", "inc.", "inc", "llc"]
    tokens = name.replace("&", "and").lower().split()
    return " ".join([t for t in tokens if t not in suffixes])


def generate_uuid() -> str:
    return str(uuid.uuid4())

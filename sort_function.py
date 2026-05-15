"""
A collection of functions for finding the cover image file within a list
of filenames/filepaths.
"""

import re
from pathlib import Path

COVER_CUES = re.compile(r"\b(?:cover|front|fc)\b", re.IGNORECASE)
NUMBERS = re.compile(r"\d+")


def score(name: str) -> tuple[int, int, str]:
    """
    Takes a name and scores its likelihood of being a cover image.
    Looks for common cover image filenames or if the name ends with
    '00'.

    Args:
        name (str): The filepath to score for the likelihood.

    Returns:
        tuple[int, int, str]: A tuple containing:
            - priority score (lower values are more likely)
            - extracted numeric hint used for sorting
            - the original filename

        Scoring rules:
            - (0, 0, name): filename matches a known cover cue or
                ends with ("00")
            - (1, n, name): filename contains 0 or 1
            - (2 + n, n, name): filename contains other numbers
            - (10, 0, name): filename contains no numbers or cover cues
    """
    stem = Path(name).stem
    lowered = stem.lower()

    if COVER_CUES.search(lowered) or lowered.endswith("00"):
        return (0, 0, name)

    numbers = [int(n) for n in NUMBERS.findall(stem)]
    for num in numbers:
        if num in (0, 1):
            return (1, num, name)

    if numbers:
        return (2 + min(numbers), min(numbers), name)

    return (10, 0, name)


def choose_cover(files: list[str]) -> str:
    """
    Selects the file most likely to be a cover image.

    Files are ranked using :func:'score', and the filename with
    the lowest score is returned.

    Args:
        files (list[str]): A list of filepaths or filenames to
        evaluate.

    Raises:
        ValueError: If 'files' is empty.

    Returns:
        str: The filename determined to be the best cover candidate.
    """
    if not files:
        raise ValueError("Empty file list")

    ranked: list[tuple[int, int, str]] = sorted(score(f) for f in files)
    return ranked[0][-1]


def sort_by_cover_likelihood(files: list[str]) -> list[str]:
    """
    Sorts files by their likelihood of being a cover image.

    Files are ordered using the ranking produced by :func:'score',
    with the most likely cover image appearing first.

    Args:
        files (list[str]): A list of filepaths or filenames to sort.

    Returns:
        list[str]: The input filenames sorted from most likely to least
        likely to be a cover image.
    """
    return [t[-1] for t in sorted(score(f) for f in files)]

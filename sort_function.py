import re
from pathlib import Path

COVER_CUES = re.compile(r"\b(?:cover|front|fc)\b", re.IGNORECASE)
NUMBERS = re.compile(r"\d+")


def score(name: str) -> tuple[int, int, str]:
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
    if not files:
        raise ValueError("Empty file list")

    ranked: list[tuple[int, int, str]] = sorted(score(f) for f in files)
    return ranked[0][-1]


def sort_by_cover_likelihood(files: list[str]) -> list[str]:
    return [t[-1] for t in sorted(score(f) for f in files)]

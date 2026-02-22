from pathlib import Path

from classes.helper_classes import ComicVineIssueStruct
from tagging.requester import RequestData
from tagging_controller import TaggingPipeline

API_KEY = "61d8fd6e7cc37cc177cd09f795e9c585999903ed"
size = 20


def tag(data: RequestData, path: str):
    tagger = TaggingPipeline(data=data, path=Path(path), size=size, api_key=API_KEY)
    tagger.run()
    return tagger.results


def check_id(id: int, data: list[ComicVineIssueStruct]) -> bool:
    if len(data) == 1:
        return True if data[0].id == id else False
    elif len(data) == 0:
        return False
    else:
        matched = False
        for result in data:
            if result.id == id:
                matched = True
                break
        return matched


def test_1():
    result = tag(
        RequestData(1, 2023, "Strange Academy", "Year One"),
        r"G:\Comics\Marvel\Strange Academy\Strange Academy Year One TPB (January 2023).cbz",
    )
    assert check_id(985028, result)


def test_2():
    result = tag(
        RequestData(1, 2022, "Dark Knights of Steel", "Dark Knights of Steel"),
        r"G:\Comics\DC\Misc\Dark Knights of Steel TPB #01 (September 2022).cbz",
    )
    assert check_id(949771, result)

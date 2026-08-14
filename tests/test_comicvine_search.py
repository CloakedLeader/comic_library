from pathlib import Path

import pytest
from my_project.classes.helper_classes import ComicVineIssueStruct
from my_project.config.config_manager import ConfigManager
from my_project.tagging.requester import RequestData
from my_project.tagging.tagging_controller import TaggingPipeline

config_man = ConfigManager(Path(r"G:\comic_library\tests\test_config.json"))
API_KEY = config_man.config.comicvine.api_key
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


# @pytest.mark.local
# def test_1():
#     result = tag(
#         RequestData(1, 2023, "Strange Academy", "Year One"),
#         r"G:\adams-comics\0 - Downloads\Strange Academy Year One TPB (January 2023).cbz",
#     )
#     assert check_id(985028, result)


@pytest.mark.local
def test_2():
    result = tag(
        RequestData(1, 2022, "Dark Knights of Steel", "Dark Knights of Steel"),
        r"G:\Comics\DC\Misc\Dark Knights of Steel TPB #01 (September 2022).cbz",
    )
    assert check_id(949771, result)

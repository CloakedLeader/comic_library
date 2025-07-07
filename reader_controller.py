from typing import Any

from reader import Comic, SimpleReader


class ReadingController:
    def __init__(self, comic: dict[str, Any]) -> None:
        self.filepath = comic["filepath"]
        self.open_windows: list[SimpleReader] = []

    def read_comic(self) -> None:
        comic_data = Comic(self.filepath)
        comic_reader = SimpleReader(comic_data)
        comic_reader.show()
        self.open_windows.append(comic_reader)

    def close_all_windows(self) -> None:
        for window in self.open_windows:
            window.close()
        self.open_windows.clear()

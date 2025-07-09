from typing import Any

from reader import Comic, SimpleReader


class ReadingController:
    """
    Controller for managing comic reading sessions and reader windows.

    This class handles the creation and management of comic reader
    instances, allowing multiple comics to be read simultaneously.
    It maintains a list of open reader windows and provides
    functionality to close them all at once.
    """

    def __init__(self, comic: dict[str, Any]) -> None:
        """
        Intialise the reading controller.

        Args:
            comic: Dictionary containing comic information
        including 'filepath' key.
        """
        self.filepath = comic["filepath"]
        self.open_windows: list[SimpleReader] = []

    def read_comic(self) -> None:
        """
        Open a new comic reader window.

        Creates a comic instance from the stored filepath, instantiates a SimpleReader,
        displays the reader window and tracks it in the open window list for
        management.
        """
        comic_data = Comic(self.filepath)
        comic_reader = SimpleReader(comic_data)
        comic_reader.show()
        self.open_windows.append(comic_reader)

    def close_all_windows(self) -> None:
        """
        Close all open reader windows and clear the tracking list.

        This method iterates through all currently open comic reader
        windows, closes them and clears the internal list of open windows.
        """
        for window in self.open_windows:
            window.close()
        self.open_windows.clear()

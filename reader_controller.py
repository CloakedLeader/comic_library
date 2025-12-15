from classes.helper_classes import GUIComicInfo
from database.gui_repo_worker import RepoWorker
from reader import Comic, SimpleReader


class ReadingController:
    """
    Controller for managing comic reading sessions and reader windows.

    This class handles the creation and management of comic reader
    instances, allowing multiple comics to be read simultaneously.
    It maintains a list of open reader windows and provides
    functionality to close them all at once.
    """

    def __init__(self) -> None:
        """
        Intialise the reading controller.

        Args:
            comic: Dictionary containing comic information including 'filepath' key.
        """
        self.open_windows: list[tuple[str, SimpleReader]] = []

    def read_comic(self, comic_data: GUIComicInfo) -> None:
        """
        Open a new comic reader window.

        Creates a comic instance from the stored filepath, instantiates a SimpleReader,
        displays the reader window and tracks it in the open window list for
        management.
        """
        with RepoWorker() as pager:
            val = pager.get_recent_page(comic_data.primary_id)
        comic = Comic(comic_data, val if val else 0)
        comic_reader = SimpleReader(comic)
        comic_reader.closed.connect(self.save_current_page)
        comic_reader.showMaximized()
        self.open_windows.append((comic_data.primary_id, comic_reader))

    def save_current_page(self, primary_id: str, page: int) -> None:
        """
        Saves the last read page to the database.

        Args:
            primary_id (str): The unique ID of the comic.
            page (int): The page to save to the database.
        """
        for entry in self.open_windows:
            if entry[0] == primary_id:
                window = entry

        with RepoWorker() as saver:
            if page == 0:
                return None
            elif page >= window[1].comic.total_pages - 1:
                saver.mark_as_finished(primary_id, page)
                return None
            else:
                saver.save_last_page(primary_id, page)
            return None
        self.window_shutdown(primary_id)
    
    def window_shutdown(self, primay_id: str):
        for entry in self.open_windows:
            if entry[0] == primay_id:
                window = entry
                window[1].close()
                self.open_windows.remove(window)

    def close_all_windows(self) -> None:
        """
        Close all open reader windows and clear the tracking list.

        This method iterates through all currently open comic reader
        windows, closes them and clears the internal list of open windows.
        """
        for window in self.open_windows:
            window[1].close()
        self.open_windows.clear()

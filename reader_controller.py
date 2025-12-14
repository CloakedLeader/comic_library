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

    def __init__(self, comic: GUIComicInfo) -> None:
        """
        Intialise the reading controller.

        Args:
            comic: Dictionary containing comic information including 'filepath' key.
        """
        self.comic_info = comic
        self.comic = Comic(comic)
        self.filepath = comic.filepath
        self.open_windows: list[tuple[str, SimpleReader]] = []

    def read_comic(self) -> None:
        """
        Open a new comic reader window.

        Creates a comic instance from the stored filepath, instantiates a SimpleReader,
        displays the reader window and tracks it in the open window list for
        management.
        """
        with RepoWorker() as pager:
            val = pager.get_recent_page(self.comic.id)
        self.comic.set_page_index(val if val else 0)
        comic_reader = SimpleReader(self.comic)
        comic_reader.closed.connect(self.save_current_page)
        comic_reader.showMaximized()
        self.open_windows.append((self.comic.id, comic_reader))

    def save_current_page(self, primary_id: str, page: int) -> None:
        """
        Saves the last read page to the database.

        Args:
            primary_id (str): The unique ID of the comic.
            page (int): The page to save to the database.
        """        
        with RepoWorker() as saver:
            if page == 0:
                return None
            elif page >= self.comic.total_pages - 1:
                saver.mark_as_finished(primary_id, page)
                return None
            saver.save_last_page(primary_id, page)
            return None

    def close_all_windows(self) -> None:
        """
        Close all open reader windows and clear the tracking list.

        This method iterates through all currently open comic reader
        windows, closes them and clears the internal list of open windows.
        """
        for window in self.open_windows:
            window[1].close()
        self.open_windows.clear()

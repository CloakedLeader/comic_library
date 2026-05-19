"""
Classes for general right click (context) menus across the app.
"""

import logging

from PySide6.QtWidgets import QMenu

from classes.helper_classes import GUIComicInfo
from database.gui_repo_worker import RepoWorker

logging.basicConfig(
    filename="debug.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


class GridViewContextMenuManager:
    """
    A class that represents the right click menu for the library grid views.

    Attributes:

        collections (list[tuple[int, str]]): A list of the comic collections in the database.
    """

    def __init__(self, collection_ids: list[int], collection_names: list[str]):
        """
        Initialises the `self.collections` attribute by zipping together two lists.

        Args:
            collection_ids (list[int]): List of the comic collection ids.
            collection_names (list[str]): List of the comic collection names.
        """
        self.collections = list(zip(collection_ids, collection_names))

    def show_menu(self, comic_info: GUIComicInfo, global_pos):
        """
        Opens the context menu with the different options such as
        `read`, `metadata` and `add to collection`.

        TODO: Add more later.

        Args:
            comic_info (GUIComicInfo): The GUIComicInfo of the clicked comic widget.
            global_pos (_type_): The position of the right click w.r.t the entire
            app view.
        """
        logging.debug(
            "Context menu requested for %s at %s", comic_info.title, global_pos
        )
        menu = QMenu()

        open_action = menu.addAction("Read")
        info_action = menu.addAction("Metadata")

        collections_menu = QMenu(title="Add to collection..")

        action_map = {}

        for coll_id, coll_name in self.collections:
            action = collections_menu.addAction(coll_name)
            action_map[action] = coll_id

        menu.addMenu(collections_menu)
        chosen_menu = menu.exec(global_pos)

        if chosen_menu == open_action:
            logging.debug(f"Read clicked for {comic_info.title}")
        elif chosen_menu == info_action:
            logging.debug(f"Metadata clicked for {comic_info.title}")
        elif chosen_menu in action_map:
            coll_id = action_map[chosen_menu]
            logging.debug(f"Add {comic_info.title} to collection {coll_id}")
            with RepoWorker() as worker:
                worker.add_to_collection(coll_id, comic_info.primary_id)
        else:
            logging.debug("Menu dismissed")

from PySide6.QtWidgets import QMenu

from database.gui_repo_worker import RepoWorker


class GridViewContextMenuManager:
    def __init__(self, collection_ids, collection_names):
        self.collections = list(zip(collection_ids, collection_names))

    def show_menu(self, comic_info, global_pos):
        print("Context menu requested for", comic_info.title, global_pos)
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
            print(f"Read clicked for {comic_info.title}")
        elif chosen_menu == info_action:
            print(f"Metadata clicked for {comic_info.title}")
        elif chosen_menu in action_map:
            coll_id = action_map[chosen_menu]
            print(f"Add {comic_info.title} to collection {coll_id}")
            with RepoWorker("D:/adams-comics/.covers") as worker:
                worker.add_to_collection(coll_id, comic_info.primary_id)
        else:
            print("Menu dismissed")

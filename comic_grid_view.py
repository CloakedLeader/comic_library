from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from classes.helper_classes import GUIComicInfo
from database.gui_repo_worker import RepoWorker
from general_comic_widget import GeneralComicWidget
from reader_controller import ReadingController
from right_click_menus import GridViewContextMenuManager


class ComicGridView(QWidget):
    metadata_requested = Signal(GUIComicInfo)

    def __init__(self, comics: list[GUIComicInfo], colums: int = 5):
        super().__init__()
        with RepoWorker("D://adams-comics//.covers") as repo_worker:
            collection_names, collection_ids = repo_worker.get_collections()
        self.context_menu = GridViewContextMenuManager(collection_ids, collection_names)
        self.comic_widgets = []
        layout = QVBoxLayout()

        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_widget.setLayout(grid_layout)
        grid_layout.setSpacing(10)
        grid_layout.setContentsMargins(10, 10, 10, 10)

        row = col = 0
        for comic in comics:
            comic_widget = GeneralComicWidget(
                comic,
                single_left_click=self.metadata_panel,
                single_right_click=self.context_menu.show_menu,
                double_left_click=self.open_reader,
                size=(180, 270),
            )
            self.comic_widgets.append(comic_widget)
            grid_layout.addWidget(
                comic_widget, row, col, alignment=Qt.AlignTop  # | Qt.AlignLeft
            )

            col += 1
            if col >= colums:
                col = 0
                row += 1

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(grid_widget)

        layout.addWidget(scroll_area)
        self.setLayout(layout)

    def open_reader(self, comic_info: GUIComicInfo):
        cont = ReadingController(comic_info)
        cont.read_comic()

    def metadata_panel(self, comic_info: GUIComicInfo):
        self.metadata_requested.emit(comic_info)

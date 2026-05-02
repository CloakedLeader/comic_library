from PySide6.QtCore import QEvent, QMimeData, QObject, QSize, Qt, Signal
from PySide6.QtGui import QDrag, QIcon
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
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

    def __init__(
        self,
        comics: list[GUIComicInfo],
        reading_controller: ReadingController,
        colums: int = 5,
        collection: bool = False,
    ):
        super().__init__()
        self.collection = collection
        self.comics = comics
        self.cont = reading_controller
        with RepoWorker() as repo_worker:
            collection_names, collection_ids = repo_worker.get_collections()
        self.context_menu = GridViewContextMenuManager(collection_ids, collection_names)
        self.comic_widgets: list[GeneralComicWidget] = []

        basic_layout = QVBoxLayout()

        self.scroll_area = self.create_scroll_area(colums)
        self.scroll_area.viewport().installEventFilter(self)

        basic_layout.addWidget(self.scroll_area)
        if collection:
            col_layout = QVBoxLayout()
            self.splitter = QSplitter()
            self.add_to_collection_button = QPushButton("Add..")
            self.add_to_collection_button.clicked.connect(self.comic_explore_window)
            col_layout.addWidget(self.scroll_area)
            col_layout.addWidget(self.add_to_collection_button)
            self.collection_content = QWidget()
            self.collection_content.setLayout(col_layout)
            self.splitter.addWidget(self.collection_content)
            fin_layout = QHBoxLayout()
            fin_layout.addWidget(self.splitter)
            self.setLayout(fin_layout)
        else:
            self.setLayout(basic_layout)

    def create_scroll_area(self, columns) -> QScrollArea:
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_widget.setLayout(self.grid_layout)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)

        row = col = 0
        for comic in self.comics:
            comic_widget = GeneralComicWidget(
                comic,
                single_left_click=self.metadata_panel,
                single_right_click=self.context_menu.show_menu,
                double_left_click=self.open_reader,
                size=(180, 270),
            )
            self.comic_widgets.append(comic_widget)
            self.grid_layout.addWidget(
                comic_widget,
                row,
                col,
                alignment=Qt.AlignmentFlag.AlignTop,  # | Qt.AlignLeft
            )

            col += 1
            if col >= columns:
                col = 0
                row += 1

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.grid_widget)
        return scroll_area

    def open_reader(self, comic_info: GUIComicInfo):
        self.cont.read_comic(comic_info)

    def metadata_panel(self, comic_info: GUIComicInfo):
        self.metadata_requested.emit(comic_info)

    def comic_explore_window(self):
        with RepoWorker() as repo_worker:
            comics = repo_worker.get_all_comics(thumb=True)
        self.all_comics = DraggableComicGridView(comics)
        self.splitter.addWidget(self.all_comics)

    def relayout_grid(self):
        width = self.scroll_area.viewport().width()
        item_width = 180 + 10
        columns = max(1, width // item_width)

        while self.grid_layout.count():
            self.grid_layout.takeAt(0)

        row = col = 0
        for widget in self.comic_widgets:
            self.grid_layout.addWidget(widget, row, col)
            col += 1
            if col >= columns:
                col = 0
                row += 1

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            watched == self.scroll_area.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            if self.collection:
                self.relayout_grid()
        return super().eventFilter(watched, event)


class DraggableComicGridView(QListWidget):
    MIME_TYPE = "application/x-comic-id"

    def __init__(self, comics: list[GUIComicInfo]):
        super().__init__()

        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)

        self.setIconSize(QSize(160, 240))
        self.setGridSize(QSize(180, 270))

        self.setSpacing(10)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

        self.setDragEnabled(True)

        for comic in comics:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, comic.primary_id)
            item.setText(comic.title)
            item.setIcon(QIcon(str(comic.cover_path)))
            item.setToolTip(comic.title)

            self.addItem(item)

    def startDrag(self, supportedActions):
        items = self.selectedItems()
        if not items:
            return

        ids = [item.data(Qt.ItemDataRole.UserRole) for item in items]

        mime = QMimeData()
        mime.setData(self.MIME_TYPE, ",".join(map(str, ids)).encode())

        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)

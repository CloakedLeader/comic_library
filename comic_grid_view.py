from PySide6.QtCore import QEvent, QMimeData, QObject, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QDrag, QDragEnterEvent, QDragMoveEvent, QDropEvent, QIcon
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


class ComicGrid(QWidget):
    metadata_requested = Signal(GUIComicInfo)

    def __init__(
        self,
        comics: list[GUIComicInfo],
        reading_controller: ReadingController,
        coll_names: list[str],
        coll_ids: list[int],
        colums: int = 5,
    ):
        super().__init__()
        self.comics = comics
        self.cont = reading_controller
        self.context_menu = GridViewContextMenuManager(coll_ids, coll_names)
        self.comic_widgets: list[GeneralComicWidget] = []

        self.columns = colums
        self.grid_layout = QGridLayout(self)
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
            if col >= self.columns:
                col = 0
                row += 1

    def add_comics(self, comics: list[GUIComicInfo]):
        start_index = len(self.comics)
        for i, comic in enumerate(comics):
            comic_widget = GeneralComicWidget(
                comic,
                single_left_click=self.metadata_panel,
                single_right_click=self.context_menu.show_menu,
                double_left_click=self.open_reader,
                size=(180, 270),
            )
            self.comic_widgets.append(comic_widget)

            index = start_index + i
            row = index // self.columns
            col = index % self.columns

            self.grid_layout.addWidget(
                comic_widget, row, col, alignment=Qt.AlignmentFlag.AlignTop
            )

    def open_reader(self, comic_info: GUIComicInfo):
        self.cont.read_comic(comic_info)

    def metadata_panel(self, comic_info: GUIComicInfo):
        self.metadata_requested.emit(comic_info)

    def relayout_grid(self, columns: int):
        self.columns = columns
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        row = col = 0
        for widget in self.comic_widgets:
            self.grid_layout.addWidget(
                widget, row, col, alignment=Qt.AlignmentFlag.AlignTop
            )
            col += 1
            if col >= self.columns:
                col = 0
                row += 1


class ComicCollectionGridView(QWidget):
    def __init__(
        self,
        comics: list[GUIComicInfo],
        reading_controller: ReadingController,
        collection_id: int,
        columns: int = 5,
    ):
        super().__init__()
        self.coll_id = collection_id
        self.col = columns
        self.comics = comics
        self.cont = reading_controller
        with RepoWorker() as repo_worker:
            collection_names, collection_ids = repo_worker.get_collections()
        self.context_menu = GridViewContextMenuManager(collection_ids, collection_names)

        self.grid = ComicGrid(
            self.comics,
            self.cont,
            collection_names,
            collection_ids,
            self.col,
        )

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.grid)
        self.scroll_area.viewport().installEventFilter(self)

        self.setAcceptDrops(True)
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

    def comic_explore_window(self):
        with RepoWorker() as repo_worker:
            comics = repo_worker.get_all_comics(thumb=True)
        self.all_comics = DraggableComicGridView(comics)
        self.splitter.addWidget(self.all_comics)

    def relayout_grid(self):
        width = self.scroll_area.viewport().width()
        item_width = 180 + 10
        columns = max(1, width // item_width)
        self.grid.relayout_grid(columns)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            watched == self.scroll_area.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            self.relayout_grid()
        return super().eventFilter(watched, event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(DraggableComicGridView.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasFormat(DraggableComicGridView.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasFormat(DraggableComicGridView.MIME_TYPE):
            data = event.mimeData().data(DraggableComicGridView.MIME_TYPE)

            ids = bytes(data.data()).decode().split(",")
            ids = [str(i) for i in ids]

            print("Dropped comics IDs: ", ids)
            self.handle_dropped_comic(ids)
        else:
            event.ignore()

    def handle_dropped_comic(self, ids: list[str]):
        with RepoWorker() as worker:
            for i in ids:
                worker.add_to_collection(self.coll_id, i)
            updated = worker.create_basemodel(ids)

        self.comics.extend(updated)
        self.grid.add_comics(updated)


class ComicGridView(QWidget):
    metadata_requested = Signal(GUIComicInfo)

    def __init__(
        self,
        comics: list[GUIComicInfo],
        reading_controller: ReadingController,
        colums: int = 5,
    ):
        super().__init__()
        self.comics = comics
        self.cont = reading_controller
        with RepoWorker() as repo_worker:
            collection_names, collection_ids = repo_worker.get_collections()
        self.context_menu = GridViewContextMenuManager(collection_ids, collection_names)

        self.grid = ComicGrid(
            self.comics, self.cont, collection_names, collection_ids, colums
        )

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.grid)
        self.scroll_area.viewport().installEventFilter(self)

        basic_layout = QVBoxLayout()
        basic_layout.addWidget(self.scroll_area)
        self.setLayout(basic_layout)

    def relayout_grid(self):
        width = self.scroll_area.viewport().width()
        item_width = 180 + 10
        columns = max(1, width // item_width)
        self.grid.relayout_grid(columns)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            watched == self.scroll_area.viewport()
            and event.type() == QEvent.Type.Resize
        ):
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
        item = items[0]
        icon = item.icon()
        pixmap = icon.pixmap(self.iconSize())
        scaled = pixmap.scaled(
            100,
            150,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        drag.setPixmap(scaled)
        drag.setHotSpot(QPoint(scaled.width() // 2, scaled.height() // 2))
        drag.exec(Qt.DropAction.CopyAction)

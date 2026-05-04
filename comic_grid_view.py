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
    """
    A class to create a grid of widgets, the grid itself is QWidget.
    """

    metadata_requested = Signal(GUIComicInfo)

    def __init__(
        self,
        comics: list[GUIComicInfo],
        reading_controller: ReadingController,
        coll_names: list[str],
        coll_ids: list[int],
        colums: int = 5,
    ):
        """
        Generates the grid of comics from an inital list of comic information. Adds
        different behaviours of the individual comic widgets on different clicks.

        Args:
            comics (list[GUIComicInfo]): The initial list of comic information to
            construct the grid from.
            reading_controller (ReadingController): The reading controller which
            allows the user to easily read the comic via a double left-click.
            coll_names (list[str]): The list of all collection names, needed for
            the right-click context menu.
            coll_ids (list[int]): The list of all collection ids, needed for the
            right-click context menu.
            colums (int, optional): The number of columns to arrange the comic
            widgets into. Defaults to 5.
        """
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
        """
        Adds comics to the grid by figuring out which row or column to place
        them in.

        Args:
            comics (list[GUIComicInfo]): The list of comic information that needs
                to be added to the grid.
        """
        start_index = len(self.comic_widgets)
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

    def clear_grid(self):
        for widget in self.comic_widgets:
            self.grid_layout.removeWidget(widget)
            widget.deleteLater()

        self.comic_widgets.clear()

    def reload_contents(self, comics: list[GUIComicInfo]):
        self.clear_grid()
        self.comics = comics

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
                alignment=Qt.AlignmentFlag.AlignTop,
            )

            col += 1
            if col >= self.columns:
                col = 0
                row += 1

    def open_reader(self, comic_info: GUIComicInfo):
        """
        Uses the passed in reading controller to open the comic with the reader.

        Args:
            comic_info (GUIComicInfo): The information of the comic to be read.
        """
        self.cont.read_comic(comic_info)

    def metadata_panel(self, comic_info: GUIComicInfo):
        """
        Opens a metadata panel on the rhs containing detailed information about
        the clicked comic.

        Args:
            comic_info (GUIComicInfo): The information of the comic that extended
                metedata must be fetched for.
        """
        self.metadata_requested.emit(comic_info)

    def relayout_grid(self, columns: int):
        """
        Rearranges the items in the grid to a certain amount of columns.

        Args:
            columns (int): The number of columns to arrange the grid items
                into.
        """
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
    """
    A class to create a grid of widgets representing the contents
    of a comic collection. Has type QWidget.
    """

    def __init__(
        self,
        comics: list[GUIComicInfo],
        reading_controller: ReadingController,
        collection_id: int,
        columns: int = 5,
    ):
        """
        Creates a grid of comics in a collection, allows drag actions to happen
        so the user can easily add comics to the collection.

        Args:
            comics (list[GUIComicInfo]): The list of comics to initially create the
            grid with.
            reading_controller (ReadingController): The application-wide reading
            controller.
            collection_id (int): The id of the specific collection the grid is showing.
            columns (int, optional): The number of columns to originally display the
            comic widgets with. Defaults to 5.
        """
        super().__init__()
        self.coll_id = collection_id
        self.col = columns
        self.comics = comics
        self.cont = reading_controller
        self.explore = False
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
        """
        Opens a window on the rhs containing all the comics in the database, of which the
        user can drag to move comics into the collection in the left-hand panel.

        If the explore panel is already open, clicking the button closes it and
        vice-versa.
        """
        if not self.explore:
            with RepoWorker() as repo_worker:
                comics = repo_worker.get_all_comics(thumb=True)
            self.all_comics = DraggableComicGridView(comics)
            self.splitter.addWidget(self.all_comics)
            self.explore = True
        else:
            self.all_comics.setParent(None)
            self.all_comics.deleteLater()
            self.explore = False

    def relayout_grid(self):
        """
        Triggered upon a resizing of the grid. Calculates the new number of columns
        given the new width of the comic grid widget.
        """
        width = self.scroll_area.viewport().width()
        item_width = 180 + 10
        columns = max(1, width // item_width)
        self.grid.relayout_grid(columns)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """
        Watches for events and checks that they are resizing evenets. If so,
        calls the resizing function.
        """
        if (
            watched == self.scroll_area.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            self.relayout_grid()
        return super().eventFilter(watched, event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """
        Watches for drag events to enter the frame of the widget, allows it to
        continue if the MIME data comes from the DraggableComicGridView.
        """
        if event.mimeData().hasFormat(DraggableComicGridView.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        """
        Watches for drag events moving across the widget,allows it to continue
        if the MIME data comes from the DraggableComicGridView.
        """
        if event.mimeData().hasFormat(DraggableComicGridView.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        """
        Watches for drop events in this widget. If the MIME data comes from the
        DraggableComicGridView, then it decodes the information and passes it to
        the handler.
        """
        if event.mimeData().hasFormat(DraggableComicGridView.MIME_TYPE):
            data = event.mimeData().data(DraggableComicGridView.MIME_TYPE)

            ids = bytes(data.data()).decode().split(",")
            ids = [str(i) for i in ids]

            print("Dropped comics IDs: ", ids)
            self.handle_dropped_comic(ids)
        else:
            event.ignore()

    def handle_dropped_comic(self, ids: list[str]):
        """
        Handles comics being dropped into the collection; ensures duplicates
        are ignored, adds the remainder to the database and updates the UI
        to display the changes.

        Args:
            ids (list[str]): The list of comic ids that were dragged into the widget.
        """
        existing_ids = {comic.primary_id for comic in self.comics}
        ids_to_add = [i for i in ids if i not in existing_ids]
        if not ids_to_add:
            return

        with RepoWorker() as worker:
            for i in ids_to_add:
                worker.add_to_collection(self.coll_id, i)
            updated = worker.create_basemodel(ids_to_add)

        self.comics.extend(updated)
        self.grid.add_comics(updated)


class ComicGridView(QWidget):
    """
    A class to represent a grid of comics with no additional, special
    functionality. Has type QWidget.
    """

    metadata_requested = Signal(GUIComicInfo)

    def __init__(
        self,
        comics: list[GUIComicInfo],
        reading_controller: ReadingController,
        colums: int = 5,
    ):
        """
        Creates the inital grid of comics.

        Args:
            comics (list[GUIComicInfo]): The list of comic information to create
            the grid from.
            reading_controller (ReadingController): The application-wide reading
            controller.
            colums (int, optional): The number of columns to arrange the grid of
            comic widgets into. Defaults to 5.
        """
        super().__init__()
        self.comics = comics
        self.cont = reading_controller
        with RepoWorker() as repo_worker:
            collection_names, collection_ids = repo_worker.get_collections()
        self.context_menu = GridViewContextMenuManager(collection_ids, collection_names)

        self.grid = ComicGrid(
            self.comics, self.cont, collection_names, collection_ids, colums
        )
        self.grid.metadata_requested.connect(self.metadata_requested.emit)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.grid)
        self.scroll_area.viewport().installEventFilter(self)

        basic_layout = QVBoxLayout()
        basic_layout.addWidget(self.scroll_area)
        self.setLayout(basic_layout)

    def relayout_grid(self):
        """
        Triggered upon a resizing of the grid. Calculates the new number of columns
        given the new width of the comic grid widget.
        """
        width = self.scroll_area.viewport().width()
        item_width = 180 + 10
        columns = max(1, width // item_width)
        self.grid.relayout_grid(columns)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """
        Watches for events and checks that they are resizing evenets. If so,
        calls the resizing function.
        """
        if (
            watched == self.scroll_area.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            self.relayout_grid()
        return super().eventFilter(watched, event)


class DraggableComicGridView(QListWidget):
    """
    A class representing a collection of comic widgets, each of which
    is draggable. Has type QListWidget.
    """

    MIME_TYPE = "application/x-comic-id"

    def __init__(self, comics: list[GUIComicInfo]):
        """
        Creates the list (which looks like a grid) of draggable comic
        widgets.

        Args:
            comics (list[GUIComicInfo]): The list of comic information to
            add into the list.
        """
        super().__init__()

        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)

        self.setIconSize(QSize(160, 240))
        self.setGridSize(QSize(180, 270))

        self.setSpacing(10)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

        self.setDragEnabled(True)
        self.set_comics(comics)
        # for comic in comics:
        #     item = QListWidgetItem()
        #     item.setData(Qt.ItemDataRole.UserRole, comic.primary_id)
        #     item.setText(comic.title)
        #     item.setIcon(QIcon(str(comic.cover_path)))
        #     item.setToolTip(comic.title)

        #     self.addItem(item)

    def startDrag(self, supportedActions):
        """
        Starts the drag event by adding MIME data to the widget and creates a
        smaller version of the comic thumbnail to follow the cursor during the drag.
        """
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

    def set_comics(self, comics: list[GUIComicInfo]):
        self.clear()

        for comic in comics:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, comic.primary_id)
            item.setText(comic.title)
            item.setIcon(QIcon(str(comic.cover_path)))
            item.setToolTip(comic.title)

            self.addItem(item)

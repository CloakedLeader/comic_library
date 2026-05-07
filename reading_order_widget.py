import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QMimeData, QPoint, QSize, Qt
from PySide6.QtGui import QDrag, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from comic_grid_view import DraggableComicGridView
from database.gui_repo_worker import RepoWorker


class ReadingOrderCreation(QDialog):
    """
    A class for a popup window which creates a reading order in the database.

    Subclasses QDialog.
    """

    def __init__(self):
        """
        Creates the standard dialog window with two text boxes, one for the
        reading order name and the other for the description.
        """
        super().__init__()

        self.main_display = QWidget()
        self.main_layout = QVBoxLayout(self.main_display)

        prompt = QLabel("Enter order title:")
        self.textbox = QLineEdit()
        self.textbox.setPlaceholderText("Reading Order..")
        self.main_layout.addWidget(prompt)
        self.main_layout.addWidget(self.textbox)
        prompt2 = QLabel("Add a description:")
        self.textbox2 = QLineEdit()
        self.textbox2.setPlaceholderText("Description..")
        self.main_layout.addWidget(prompt2)
        self.main_layout.addWidget(self.textbox2)

        self.create_coll = QPushButton("Create order")
        self.create_coll.clicked.connect(self.create_order)
        self.exit_button = QPushButton("Cancel")
        self.exit_button.clicked.connect(self.reject)
        button_holder = QWidget()
        button_layout = QHBoxLayout(button_holder)
        button_layout.addWidget(self.create_coll)
        button_layout.addWidget(self.exit_button)
        self.main_layout.addWidget(button_holder)

        self.setLayout(self.main_layout)

    def create_order(self):
        """
        Creates the database with the text inside the text boxes.
        This function is triggered when the user presses the "Create order"
        button. After the database has been written to, the dialog window
        closes.
        """
        name = self.textbox.text()
        description = self.textbox2.text()

        with RepoWorker() as worker:
            if description == "":
                description = None
            worker.create_reading_order(name, description)

        self.close()


class ReadingOrderList(QListWidget):
    """
    A class for representing an order of comic widgets.
    This subclasses QListWidget.
    """

    MIME_TYPE = "application/x-comic-order-id"

    def __init__(self, order_id: int, order_name: str):
        """
        Creates the original reading order just from information
        collected from the database. Adds the widgets in the order
        taken from the database.

        Args:
            order_id (int): The id of the reading order to query the db for.
            order_name (str): The name of the reading order for display
            purposes.
        """
        super().__init__()
        self.order_id = order_id
        self.order_name = order_name

        self.setAcceptDrops(True)
        self.setWindowTitle("Draggable List")
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        self.create_list_items()

    def get_db_order(self) -> Optional[list[tuple[str, int]]]:
        """
        Gets the current reading order from the database. Queries the
        database each time this is called to remove stale data.

        Returns:
            Optional[list[tuple[str, int]]]: The list which represents
            the ordered comics, None if there are no comics in the database
            or the database does not exist.
        """
        # ? Perhaps this can be removed and just called directly?
        with RepoWorker() as worker:
            return worker.get_order_contents(self.order_id)

    def create_list_items(self) -> None:
        """
        Creates the display of comic widgets. For each comic in the ordered
        list it adds a small image to the left and the name of the comic in
        the middle.
        """
        order = self.get_db_order()
        if order is None:
            ids_in_order = []
        else:
            ids_in_order = [c[0] for c in order]
        with RepoWorker() as worker:
            comic_info = worker.create_basemodel(ids_in_order, thumb=True)
        for comic in comic_info:
            item = QListWidgetItem(comic.title)
            item.setData(Qt.ItemDataRole.UserRole, comic.primary_id)
            item.setSizeHint(QSize(100, 180))
            pixmap = self.get_comic_icon(comic.cover_path)
            item.setData(Qt.ItemDataRole.DecorationRole, pixmap)
            self.addItem(item)

    def get_current_order(self) -> list[str]:
        """
        Gets the current order of comics in the display after the user
        has moved them around.

        Returns:
            list[str]: A list of the comic_id's where the order of the list
            is the order of the comics also.
        """
        ids = []
        for i in range(self.count()):
            item = self.item(i)
            ids.append(item.data(Qt.ItemDataRole.UserRole))
        return ids

    def get_position(self, comic_id: str) -> int:
        """
        Finds the position in the list of a certain comic widget.

        Args:
            comic_id (str): The comic id to look for in the list.

        Raises:
            ValueError: Occurs if the comic id cannot be found anywhere
            in the list, so there must be stale data somewhere.

        Returns:
            int: The position of the comic widget, zero indexed.
        """
        # ? Is zero-indexing here wrong? Should we start from 1?
        for i in range(self.count()):
            if self.item(i).data(Qt.ItemDataRole.UserRole) == comic_id:
                return i
        raise ValueError("Cannot find widget in current list.")

    def move_item(self, start: int, end: int):
        """
        Moves the position of a widget within the list.

        Args:
            start (int): The position in the list of the widget to be moved.
            end (int): The position to move the widget to.
        """
        if start == end:
            return

        item = self.takeItem(start)
        widget = self.itemWidget(item)
        self.removeItemWidget(item)
        self.insertItem(end, item)
        self.setItemWidget(item, widget)

    def add_comic(self, comic_id: str, row: int):
        """
        Adds a new comic to the list in the provided position.

        Args:
            comic_id (str): The ID of the comic to be added so
            its information can be taken from the database.
            row (int): The position in the list to input the new
            widget into.
        """
        if self.contains_comic(comic_id):
            return

        with RepoWorker() as worker:
            comic = worker.create_basemodel([comic_id], thumb=True)[0]

        item = QListWidgetItem(comic.title)
        item.setData(Qt.ItemDataRole.UserRole, comic_id)
        item.setSizeHint(QSize(100, 180))
        pixmap = self.get_comic_icon(comic.cover_path)

        item.setData(Qt.ItemDataRole.DecorationRole, pixmap)
        self.insertItem(row, item)

    def contains_comic(self, comic_id: str) -> bool:
        """
        Checks whether a certain comic is already in the list.

        Args:
            comic_id (str): The ID of the comic to check.

        Returns:
            bool: True if already in the list, False if not.
        """
        for i in range(self.count()):
            if self.item(i).data(Qt.ItemDataRole.UserRole) == comic_id:
                return True
        return False

    def startDrag(self, supportedActions) -> None:
        """
        Starts a drag action by encoding MIME data and creates a mini image
        to follow the cursor.

        The MIME data is a dictionary with keys, "comic_ids" and "positions", both
        of which have values which are lists of ID's and position's respectively.
        They are in the same order, so that the lists line out.

        They are lists but there should only be one widget dragged at a time by the
        user.
        """
        items = self.selectedItems()
        if not items:
            return

        ids = [item.data(Qt.ItemDataRole.UserRole) for item in items]
        positions = []
        for i in ids:
            positions.append(self.get_position(i))
        payload = {"comic_ids": ids, "positions": positions}

        mime = QMimeData()
        mime.setData(self.MIME_TYPE, json.dumps(payload).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        item = items[0]
        pixmap = item.data(Qt.ItemDataRole.DecorationRole)
        scaled = pixmap.scaled(
            120,
            180,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        drag.setPixmap(scaled)
        drag.setHotSpot(QPoint(scaled.width() // 2, scaled.height() // 2))
        drag.exec(Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event) -> None:
        """
        Allows a drag action from this widget, or from the DraggableComicGridView.
        """
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
        elif event.mimeData().hasFormat(DraggableComicGridView.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        """
        Allows a drag action from this widget, or from the DraggableComicGridView.
        """
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
        elif event.mimeData().hasFormat(DraggableComicGridView.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        """
        This is where the logic for the drop event is dispatched.

        There are two paths, either the frop is from this widget,
        or from the DraggableComicGridView. The former leads to a
        re-ordering of the list and latter adds a comic into the
        list.
        """
        if event.mimeData().hasFormat(self.MIME_TYPE):
            data = event.mimeData().data(self.MIME_TYPE)
            payload = json.loads(bytes(data).decode())

            comic_ids = payload["comic_ids"]
            positions = payload["positions"]
            if len(comic_ids) != 1:
                return

            insert_row = self.indexAt(event.position().toPoint()).row()
            if insert_row < 0:
                insert_row = self.count()
            for i in comic_ids and positions:
                self.move_item(i, insert_row)
            event.acceptProposedAction()

        elif event.mimeData().hasFormat(DraggableComicGridView.MIME_TYPE):
            data = event.mimeData().data(DraggableComicGridView.MIME_TYPE)
            comic_ids = bytes(data.data()).decode().split(",")
            comic_ids = [str(i) for i in comic_ids]
            insert_row = self.indexAt(event.position().toPoint()).row()
            if insert_row < 0:
                insert_row = self.count()
            for i in comic_ids:
                self.add_comic(i, insert_row)
            event.acceptProposedAction()
        else:
            event.ignore()

    @staticmethod
    def get_comic_icon(image_path: Path) -> QPixmap:
        """
        Gets the image from a filepath and then scales it down
        to fit inside the comic list widgets.

        Args:
            image_path (Path): The path of the image file.

        Returns:
            QPixmap: The QPixmap of the scaled image.
        """
        pixmap = QPixmap(str(image_path))
        return pixmap.scaled(
            QSize(120, 160),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )


class ReadingOrderEditor(QWidget):
    """
    A class that represents an editor for a reading order.
    Combining an ordered list of the current comics in the order
    on the left and the full collection of comics in the library
    on the right.

    It is of QWidget type.
    """

    def __init__(self, order_id: int, order_title: str):
        """
        Creates the main widget. Containing a splitter so that the
        proportions of the different components can be adjusted.

        Args:
            order_id (int): The id of the reading order being edited.
            order_title (str): The description of the reading order.
        """
        super().__init__()
        self.order_id = order_id
        self.order_title = order_title

        dummy_layout = QHBoxLayout(self)
        # main_layout.setSpacing(12)
        self.splitter = QSplitter()
        with RepoWorker() as worker:
            all_comics = worker.get_all_comics()

        self.library_panel = DraggableComicGridView(all_comics)
        self.order_panel = ReadingOrderList(order_id, order_title)
        self.save_button = QPushButton("Save Current Order")
        self.left_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_widget)
        self.left_layout.addWidget(self.order_panel)
        self.left_layout.addWidget(self.save_button)
        self.save_button.clicked.connect(self.save_order)
        self.splitter.addWidget(self.left_widget)
        self.splitter.addWidget(self.library_panel)
        dummy_layout.addWidget(self.splitter)

    def save_order(self):
        """Saves the currently displayed reading order to the database."""
        order = self.order_panel.get_current_order()
        with RepoWorker() as repo:
            repo.add_to_order(self.order_id, order)


class ReadingOrderView(QWidget):
    pass

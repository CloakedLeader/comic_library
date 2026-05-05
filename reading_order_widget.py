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
    def __init__(self):
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
        name = self.textbox.text()
        description = self.textbox2.text()

        with RepoWorker() as worker:
            if description == "":
                description = None
            order_int = worker.create_reading_order(name, description)

        self.open_order_creation(order_int, name)
        self.close()

    def open_order_creation(self, order_id: int, order_title: str):
        self.order_editor = ReadingOrderEditor(order_id, order_title)
        self.order_editor.show()


class CustomListWidget(QWidget):
    def __init__(self, name: str, image_path: Path):
        super().__init__()
        self.setFixedHeight(100)
        image_label = QLabel()
        image_label.setFixedSize(120, 160)
        image_label.setScaledContents(True)
        image_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.pixmap = QPixmap(str(image_path))
        self.pixmap = self.pixmap.scaled(
            image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        image_label.setPixmap(self.pixmap)

        name_label = QLabel(name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(image_label)
        main_layout.addWidget(name_label)
        self.setLayout(main_layout)


class ReadingOrderList(QListWidget):
    MIME_TYPE = "application/x-comic-order-id"

    def __init__(self, order_id: int, order_name: str):
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
        with RepoWorker() as worker:
            return worker.get_order_contents(self.order_id)

    def create_list_items(self) -> None:
        order = self.get_db_order()
        if order is None:
            ids_in_order = []
        else:
            ids_in_order = [c[0] for c in order]
        with RepoWorker() as worker:
            comic_info = worker.create_basemodel(ids_in_order, thumb=True)
        # comic_info.reverse()
        for comic in comic_info:
            item = QListWidgetItem(comic.title)
            item.setData(Qt.ItemDataRole.UserRole, comic.primary_id)
            item.setSizeHint(QSize(100, 180))
            pixmap = self.get_comic_icon(comic.cover_path)
            item.setData(Qt.ItemDataRole.DecorationRole, pixmap)
            self.addItem(item)

    def get_current_order(self) -> list[str]:
        ids = []
        for i in range(self.count()):
            item = self.item(i)
            ids.append(item.data(Qt.ItemDataRole.UserRole))
        return ids

    def get_position(self, comic_id: str) -> int:
        for i in range(self.count()):
            if self.item(i).data(Qt.ItemDataRole.UserRole) == comic_id:
                return i
        raise ValueError("Cannot find widget in current list.")

    def move_item(self, start: int, end: int):
        if start == end:
            return

        item = self.takeItem(start)
        widget = self.itemWidget(item)
        self.removeItemWidget(item)
        self.insertItem(end, item)
        self.setItemWidget(item, widget)

    def add_comic(self, comic_id: str, row: int):
        if self.contains_comic(comic_id):
            return

        with RepoWorker() as worker:
            comic = worker.create_basemodel([comic_id], thumb=True)[0]

        item = QListWidgetItem(comic.title)
        item.setData(Qt.ItemDataRole.UserRole, comic_id)
        item.setSizeHint(QSize(100, 180))
        pixmap = self.get_comic_icon(comic.cover_path)

        # widget = CustomListWidget(name=comic.title, image_path=comic.cover_path)
        item.setData(Qt.ItemDataRole.DecorationRole, pixmap)
        # self.setItemWidget(item, widget)
        self.insertItem(row, item)

    def contains_comic(self, comic_id: str) -> bool:
        for i in range(self.count()):
            if self.item(i).data(Qt.ItemDataRole.UserRole) == comic_id:
                return True
        return False

    def startDrag(self, supportedActions) -> None:
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
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
        elif event.mimeData().hasFormat(DraggableComicGridView.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
        elif event.mimeData().hasFormat(DraggableComicGridView.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
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

    @staticmethod
    def get_comic_icon(image_path: Path) -> QPixmap:
        pixmap = QPixmap(str(image_path))
        return pixmap.scaled(
            QSize(120, 160),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )


class ReadingOrderEditor(QWidget):
    def __init__(self, order_id: int, order_title: str):
        super().__init__()
        self.order_id = order_id
        self.order_title = order_title

        # self.setWindowTitle("Edit Reading Order")
        # self.resize(1200, 800)

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
        order = self.order_panel.get_current_order()
        # print("The current order is: ", order)
        with RepoWorker() as repo:
            repo.add_to_order(self.order_id, order)


class ReadingOrderView(QWidget):
    pass

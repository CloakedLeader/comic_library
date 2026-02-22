from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
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
        pixmap = QPixmap(str(image_path))
        image_label.setFixedSize(50, 80)
        image_label.setScaledContents(True)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setPixmap(
            pixmap.scaled(
                image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

        name_label = QLabel(name)

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(image_label)
        main_layout.addWidget(name_label)


class ReadingOrderListEditor(QListWidget):
    MIME_TYPE = "application/x-comic-id"

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
        comic_info.reverse()
        for comic in comic_info:
            item = QListWidgetItem()
            widget = CustomListWidget(name=comic.title, image_path=comic.cover_path)
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, comic.primary_id)
            self.addItem(item)
            self.setItemWidget(item, widget)

    def get_current_order(self) -> list[str]:
        ids = []
        for i in range(self.count()):
            item = self.item(i)
            ids.append(item.data(Qt.ItemDataRole.UserRole))
        return ids

    def add_comic(self, comic_id: str, row: int):
        if self.contains_comic(comic_id):
            return

        with RepoWorker() as worker:
            comic = worker.create_basemodel([comic_id], thumb=True)[0]

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, comic_id)
        item.setSizeHint(QSize(180, 270))

        widget = CustomListWidget(name=comic.title, image_path=comic.cover_path)

        self.insertItem(row, item)
        self.setItemWidget(item, widget)

    def contains_comic(self, comic_id: str) -> bool:
        for i in range(self.count()):
            if self.item(i).data(Qt.ItemDataRole.UserRole) == comic_id:
                return True
        return False

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasFormat(self.MIME_TYPE):
            event.ignore()
            return

        comic_id = str(bytes(event.mimeData().data(self.MIME_TYPE)).decode())

        insert_row = self.indexAt(event.position().toPoint()).row()
        if insert_row < 0:
            insert_row = self.count()

        self.add_comic(comic_id, insert_row)
        event.acceptProposedAction()


class ReadingOrderEditor(QWidget):
    def __init__(self, order_id: int, order_title: str):
        super().__init__()
        self.order_id = order_id

        self.setWindowTitle("Edit Reading Order")
        self.resize(1200, 800)

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(12)

        with RepoWorker() as worker:
            all_comics = worker.get_all_comics()

        self.library_panel = DraggableComicGridView(all_comics)
        self.order_panel = ReadingOrderListEditor(order_id, order_title)

        main_layout.addWidget(self.library_panel, 3)
        main_layout.addWidget(self.order_panel, 2)


class ReadingOrderView(QWidget):
    pass

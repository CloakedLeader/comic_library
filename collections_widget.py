from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from typing import Callable

from database.gui_repo_worker import RepoWorker


class CollectionButton(QWidget):
    clicked = Signal(int)
    doubleClicked = Signal()

    def __init__(self, name: str, collection_id: int, parent=None):
        super().__init__(parent)
        self.collection = collection_id
        self.setAttribute(Qt.WA_StyledBackground, True)

        style_sheet = """
            #comicCard {
                background-color: #f0f0f0;

                border: 1px solid #ccc;

                border-radius: 6px;
                padding: 8px;
            }
            #comicCard:hover {

                background-color: #f5f5f5;
            }
            """

        self.button_layout = QHBoxLayout()
        self.button_layout.addWidget(QLabel(name))

        self.setObjectName("comicCard")
        self.setStyleSheet(style_sheet)
        self.setLayout(self.button_layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.collection)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit()


class CollectionDisplay(QWidget):
    def __init__(
            self,
            titles: list[str],
            collection_ids: list[int],
            left_clicked: Callable,):
        super().__init__()

        layout = QVBoxLayout()
        layout.setSpacing(4)
        container = QWidget()
        container.setLayout(layout)

        combined = list(zip(titles, collection_ids))

        for title, id in combined:
            widget = CollectionButton(title, id, self)
            widget.clicked.connect(left_clicked)
            widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            layout.addWidget(widget)

        self.setLayout(layout)


class CollectionCreation(QDialog):
    def __init__(self):
        super().__init__()

        self.main_display = QWidget()
        self.main_layout = QVBoxLayout(self.main_display)

        prompt = QLabel("Enter collection title:")
        self.textbox = QLineEdit()
        self.textbox.setPlaceholderText("Collection..")
        self.main_layout.addWidget(prompt)
        self.main_layout.addWidget(self.textbox)

        self.create_coll = QPushButton("Create collection")
        self.create_coll.clicked.connect(self.create_collection)
        self.exit_button = QPushButton("Cancel")
        self.exit_button.clicked.connect(self.reject)
        button_holder = QWidget()
        button_layout = QHBoxLayout(button_holder)
        button_layout.addWidget(self.create_coll)
        button_layout.addWidget(self.exit_button)
        self.main_layout.addWidget(button_holder)

        self.setLayout(self.main_layout)

    def create_collection(self):
        name = self.textbox.text()
        with RepoWorker("D:/adams-comics/.covers") as worker:
            worker.create_collection(name)
        self.accept()

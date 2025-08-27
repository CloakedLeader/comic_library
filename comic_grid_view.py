import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from classes.helper_classes import GUIComicInfo
from reader_controller import ReadingController


class ComicWidget(QWidget):
    clicked = Signal()
    doubleClicked = Signal()

    def __init__(self, comic_info: GUIComicInfo):
        super().__init__()

        self.comic_info = comic_info
        layout = QVBoxLayout()
        cover_label = QLabel()
        cover_label.setFixedSize(90, 135)
        cover_label.setMaximumSize(150, 225)
        cover_label.setAlignment(Qt.AlignCenter)

        if os.path.exists(self.comic_info.cover_path):
            pixmap = QPixmap(self.comic_info.cover_path)
            if not pixmap.isNull():
                cover_label.setPixmap(
                    pixmap.scaled(120, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
            else:
                cover_label.setText("No Cover")

        title_label = QLabel(self.comic_info.title)
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(cover_label)
        layout.addWidget(title_label)

        self.setLayout(layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit()


class ComicGridView(QWidget):
    metadata_requested = Signal(GUIComicInfo)

    def __init__(
        self, comics: list[GUIComicInfo], colums: int = 5, max_items: int = 20
    ):
        super().__init__()
        self.comic_widgets = []
        layout = QVBoxLayout()

        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_widget.setLayout(grid_layout)
        grid_layout.setSpacing(10)
        grid_layout.setContentsMargins(10, 10, 10, 10)

        width = 150
        height = 225

        row = col = 0
        for comic in comics:
            comic_widget = ComicWidget(comic)
            comic_widget.setFixedSize(width, height)
            comic_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            comic_widget.clicked.connect(lambda c=comic: self.metadata_panel(c))
            comic_widget.doubleClicked.connect(lambda c=comic: self.open_reader(c))
            self.comic_widgets.append(comic_widget)
            grid_layout.addWidget(
                comic_widget, row, col, alignment=Qt.AlignTop | Qt.AlignLeft
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

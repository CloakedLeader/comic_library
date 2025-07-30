from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGridLayout, QScrollArea
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
import os

from helper_classes import GUIComicInfo


class ComicGridView(QWidget):
    def __init__(self, comics: list[GUIComicInfo], colums: int = 5):
        super().__init__()
        layout = QVBoxLayout()

        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setSpacing(10)

        row = col = 0
        for comic in comics:
            comic_widget = self.create_comic_widget(comic)
            grid_layout.addWidget(comic_widget, row, col)

            col += 1
            if col >= colums:
                col = 0
                row += 1

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(grid_widget)

        layout.addWidget(scroll_area)
        self.setLayout(layout)

    def create_comic_widget(self, comic: GUIComicInfo) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        cover_label = QLabel()
        cover_label.setFixedSize(120, 180)
        cover_label.setAlignment(Qt.AlignCenter)

        if os.path.exists(comic.cover_path):
            pixmap = QPixmap(comic.cover_path)
            if not pixmap.isNull():
                cover_label.setPixmap(
                    pixmap.scaled(120, 180,
                                  Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                cover_label.setText("No Cover")

        title_label = QLabel(comic.title)
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(cover_label)
        layout.addWidget(title_label)

        return widget

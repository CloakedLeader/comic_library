import zipfile
from io import BytesIO
from pathlib import Path

import requests
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tagging_controller import RequestData


class ComicMatcherUI(QDialog):
    def __init__(
        self, actual_info: RequestData, best_matches: list[dict], filepath: Path
    ):
        super().__init__()
        self.actual_data = actual_info
        self.filepath = filepath
        self.matches = best_matches

        self.main_display = QWidget()
        self.main_layout = QVBoxLayout(self.main_display)

        self.actual_comic = self.create_actual_data_widget()
        self.comic_matches = self.create_matches_widget()
        self.tag = QPushButton("Confirm Match")
        self.tag.clicked.connect(self.confirm_match)
        self.exit_button = QPushButton("Close")
        self.exit_button.addAction(self.reject)

        self.content = QWidget()
        self.content_layout = QHBoxLayout(self.content)
        self.content_layout.addWidget(self.actual_comic)
        self.content_layout.addWidget(self.comic_matches)
        self.button_holder = QWidget()
        self.button_layout = QHBoxLayout(self.button_holder)
        self.button_layout.addWidget(self.tag, alignment=Qt.AlignRight)
        self.button_layout.addWidget(self.exit_button, alignment=Qt.AlignRight)
        self.main_layout.addWidget(self.content, stretch=9)
        self.main_layout.addWidget(self.button_holder, stretch=1)

        self.setLayout(self.main_layout)

    def create_actual_data_widget(self) -> QWidget:
        cover_bytes = self.cover_getter(self.filepath)
        pixmap = QPixmap()
        pixmap.loadFromData(cover_bytes.getvalue())
        title = self.actual_data.unclean_title
        year = self.actual_data.pub_year
        number = self.actual_data.num
        actual_widget = QWidget()
        layout = QVBoxLayout(actual_widget)
        layout.addWidget(QLabel("Your Comic"))
        layout.addWidget(pixmap)
        layout.addWidget(QLabel(title))
        layout.addWidget(QLabel(year))
        layout.addWidget(QLabel(number))

        return actual_widget

    def create_matches_widget(self) -> QWidget:
        cover_pixmaps = []

        self.table_widget = QTableWidget(len(self.matches), 3)
        self.table_widget.setSelectionBehavior(QTableWidget.selectRow)

        row_index = 0
        for match in self.matches:
            if match.get("cover_link"):
                cover_pixmaps.append(
                    self.load_pixmap_from_url(str(match.get("cover_link")))
                )
            title_item = QTableWidgetItem(match["title"] + ":" + match["series"])
            year_item = QTableWidgetItem(match["year"])
            number_item = QTableWidgetItem(match["number"])
            for index, item in enumerate([title_item, year_item, number_item]):
                self.table_widget.setItem(row_index, index, item)
            row_index += 1

        self.table_widget.cellClicked.connect(self.on_row_clicked)

        self.cover_display = QStackedWidget()
        for img in cover_pixmaps:
            self.cover_display.addWidget(QLabel(pixmap=img))
        self.cover_display.setCurrentIndex(0)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.cover_display)
        layout.addWidget(self.table_widget)

        return container

    def on_row_clicked(self, row, column):
        self.cover_display.setCurrentIndex(row)

    def confirm_match(self):
        row = self.table_widget.currentRow()
        if row != -1:
            print(f"Selected row: {row}")
        else:
            print("No row selected")

    @staticmethod
    def cover_getter(filepath):
        with zipfile.ZipFile(filepath, "r") as zip_ref:
            image_files = [
                f
                for f in zip_ref.namelist()
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if not image_files:
                print("Empty archive.")
                return
            image_files.sort()
            cover = zip_ref.read(image_files[0])
            return BytesIO(cover)

    @staticmethod
    def load_pixmap_from_url(url: str) -> QPixmap:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            image_data = BytesIO(response.content)
            pixmap = QPixmap()
            if pixmap.loadFromData(image_data.read()):
                return pixmap
        except Exception as e:
            print(f"Failed to load image from {url}: {e}")
        fallback = QPixmap(120, 180)
        fallback.fill(Qt.gray)
        return fallback

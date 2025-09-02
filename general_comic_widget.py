from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from typing import Optional, Callable
import os
import requests
from io import BytesIO

from classes.helper_classes import RSSComicInfo, GUIComicInfo


class GeneralComicWidget(QWidget):
    left_clicked = Signal()
    right_clicked = Signal()
    double_clicked = Signal()

    pixmap_cache: dict[str, QPixmap] = {}

    @classmethod
    def get_cached_pixmap(cls, key: str) -> Optional[QPixmap]:
        return cls.pixmap_cache.get(key)
    
    @classmethod
    def set_cached_pixmap(cls, key: str, pixmap: QPixmap):
        cls.pixmap_cache[key] = pixmap

    def __init__(
            self,
            comic_info: RSSComicInfo | GUIComicInfo,
            single_left_click: Callable,
            single_right_click: Callable,
            double_left_click: Callable,
            ):
        super().__init__()
        self.comic_info = comic_info
        layout = QVBoxLayout()
        cover_label = QLabel()
        cover_label.setFixedHeight(135)
        cover_label.setAlignment(Qt.AlignCenter)

        cover_path_or_url = comic_info.cover_path or comic_info.cover_url
        pixmap = self.get_cached_pixmap(cover_path_or_url)
        if not pixmap:
            if isinstance(self.comic_info, GUIComicInfo):
                if os.path.exists(cover_path_or_url):
                    pixmap = QPixmap(cover_path_or_url)
            elif isinstance(self.comic_info, RSSComicInfo):
                pixmap = self.load_pix_from_link(cover_path_or_url)

        if pixmap and not pixmap.isNull():
            pixmap = pixmap.scaled(120, 180, Qt.KeepAspectRation, Qt.SmoothTransition)
            self.set_cached_pixmap(cover_path_or_url, pixmap)
        else:
            pixmap = QPixmap(120, 180)
            pixmap.fill(Qt.gray)

        cover_label.setPixmap(pixmap)

        title_label = QLabel(self.comic_info.title)
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(cover_label)
        layout.addWidget(title_label)

        self.left_clicked.connect(lambda c=self.comic_info: single_left_click(c))
        self.right_clicked.connect(lambda c=self.comic_info: single_right_click(c))
        self.double_clicked.connect(lambda c=self.comic_info: double_left_click(c))

        self.setToolTip(self.comic_info.title)
        self.setLayout(layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.left_clicked.emit()
        if event.button() == Qt.RightButton:
            self.right_clicked.emit()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()

    @staticmethod
    def load_pix_from_link(link) -> Optional[QPixmap]:
        try:
            response = requests.get(link, timeout=30)
            response.raise_for_status()
            image_data = BytesIO(response.content)
            pixmap = QPixmap()
            if pixmap.loadFromData(image_data.read()):
                return pixmap
        except Exception as e:
            print(f"Failed to load image from {link}: {e}")
        return None

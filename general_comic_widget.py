from io import BytesIO
from pathlib import Path
from typing import Callable, Optional

import requests
from PySide6.QtCore import (
    QObject,
    QPoint,
    QRect,
    QRunnable,
    Qt,
    QThreadPool,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from classes.helper_classes import GUIComicInfo, RSSComicInfo


class GeneralComicWidget(QWidget):
    left_clicked = Signal(object)
    right_clicked = Signal(object, QPoint)
    double_clicked = Signal(object)
    image_loaded = Signal(QPixmap)

    thread_pool = QThreadPool()

    pixmap_cache: dict[str, QPixmap] = {}

    @classmethod
    def get_cached_pixmap(cls, key: str | Path) -> Optional[QPixmap]:
        return cls.pixmap_cache.get(str(key))

    @classmethod
    def set_cached_pixmap(cls, key: str | Path, pixmap: QPixmap):
        cls.pixmap_cache[str(key)] = pixmap

    def __init__(
        self,
        comic_info: RSSComicInfo | GUIComicInfo,
        single_left_click: Optional[Callable] = None,
        single_right_click: Optional[Callable] = None,
        double_left_click: Optional[Callable] = None,
        size: tuple[int, int] = (200, 300),
        progress: Optional[float] = None,
    ):
        super().__init__()
        self.comic_info = comic_info
        self.size_ = width, height = size
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)

        self.cover_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)

        if isinstance(comic_info, RSSComicInfo):
            placeholder = QPixmap(width, height)
            placeholder.fill(Qt.GlobalColor.darkGray)
            self.cover_label.setPixmap(placeholder)
            self.image_loaded.connect(self.on_image_ready)
            self.load_image_async(comic_info.cover_url)

        else:
            cover_path = comic_info.cover_path
            pixmap = self.get_cached_pixmap(cover_path)
            if not pixmap and cover_path.exists():
                pixmap = QPixmap(cover_path)
                self.set_cached_pixmap(cover_path, pixmap)
            if pixmap and not pixmap.isNull():
                pixmap = pixmap.scaled(
                    width,
                    height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            else:
                pixmap = QPixmap(width, height)
                pixmap.fill(Qt.GlobalColor.darkGray)

            if progress:
                pixmap = self.add_read_progress(pixmap, progress)

            self.cover_label.setPixmap(pixmap)

        title_label = QLabel(self.comic_info.title)
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.cover_label)
        layout.addWidget(title_label)

        if single_left_click is not None:
            self.left_clicked.connect(single_left_click)
        if single_right_click is not None:
            self.right_clicked.connect(single_right_click)
        if double_left_click is not None:
            self.double_clicked.connect(double_left_click)

        self.setToolTip(self.comic_info.title)
        self.setLayout(layout)

    def load_image_async(self, url: str):
        pixmap = self.get_cached_pixmap(url)
        if pixmap:
            self.on_image_ready(url, pixmap)
            return

        result = ImageResult()
        result.finished.connect(self.on_worker_finished)
        worker = ImageWorker(url, result)
        self.thread_pool.start(worker)

    def on_worker_finished(self, url: str, pixmap: QPixmap):
        self.set_cached_pixmap(url, pixmap)
        if isinstance(self.comic_info, RSSComicInfo):
            cover_url = self.comic_info.cover_url
            if cover_url == url:
                self.on_image_ready(url, pixmap)

    def on_image_ready(self, url: str, pixmap: QPixmap):
        cover = (
            self.comic_info.cover_url
            if isinstance(self.comic_info, RSSComicInfo)
            else None
        )
        if url != cover:
            return
        w, h = self.size_
        scaled = pixmap.scaled(
            w,
            h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.cover_label.setPixmap(scaled)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.left_clicked.emit(self.comic_info)
        if event.button() == Qt.MouseButton.RightButton:
            print("Right click detected on", self.comic_info.title)
            self.right_clicked.emit(self.comic_info, event.globalPos())

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.comic_info)

    @staticmethod
    def add_read_progress(pixmap: QPixmap, progress: float) -> QPixmap:
        painted = QPixmap(pixmap)

        bar_height = max(6, painted.height() // 20)
        bar_width = int(painted.width() * min(progress, 1.0))

        painter = QPainter(painted)

        painter.fillRect(
            QRect(0, painted.height() - bar_height, painted.width(), bar_height),
            QColor(50, 50, 50, 180),
        )

        painter.fillRect(
            QRect(0, painted.height() - bar_height, bar_width, bar_height),
            QColor(0, 200, 0, 220),
        )

        painter.end()
        return painted


class ImageResult(QObject):
    finished = Signal(str, QPixmap)


class ImageWorker(QRunnable):
    def __init__(self, url: str, results: ImageResult) -> None:
        super().__init__()
        self.url = url
        self.result = results

    @Slot()
    def run(self) -> None:
        try:
            response = requests.get(self.url, timeout=30)
            response.raise_for_status()
            image_data = BytesIO(response.content)
            pixmap = QPixmap()
            pixmap.loadFromData(image_data.read())
            self.result.finished.emit(self.url, pixmap)
        except Exception as e:
            print(f"Failed to load image from {self.url}: {e}")
        return None

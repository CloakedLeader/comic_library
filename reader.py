import os
import zipfile
from collections import OrderedDict
from functools import partial
from io import BytesIO

from PIL import Image
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QToolBar,
    QToolButton,
    QWidget,
)

# from metadata_gui_panel import MetadataDialog
from file_utils import get_name
from gui_repo_worker import RepoWorker
from helper_classes import GUIComicInfo
from metadata_gui_panel import MetadataDialog


class ComicError(Exception):
    """Base exception for Comic-related issues."""


class PageIndexError(ComicError):
    """Raised when a page index is out of range."""


class ImageLoadError(ComicError):
    """Raised when an image fails to load."""


class Comic:

    def __init__(
        self, comic_info: GUIComicInfo, start_index: int = 0, max_cache: int = 10
    ) -> None:
        self.path = comic_info.filepath
        self.filename = get_name(comic_info.filepath)
        self.zip = zipfile.ZipFile(comic_info.filepath, "r")
        self.image_names = sorted(
            name
            for name in self.zip.namelist()
            if name.lower().endswith((".jpg", ".jpeg", ".png"))
        )
        if not self.image_names:
            raise ComicError("No images found in the file.")
        self.total_pages = len(self.image_names)
        self.size = os.path.getsize(comic_info.filepath)
        self.cache: OrderedDict[str, bytes] = OrderedDict()
        self.max_cache = max_cache
        self.current_index: int = start_index
        self.id = comic_info.primary_id
        self.info = comic_info

    def get_image_data(self, index: int) -> bytes:
        if index < 0 or index >= self.total_pages:
            raise PageIndexError(f"Index {index} out of range.")

        name = self.image_names[index]
        if name in self.cache:
            self.cache.move_to_end(name)
            return self.cache[name]

        try:
            with self.zip.open(name) as file:
                data = file.read()
        except Exception as e:
            raise ImageLoadError(f"Failed to read image {name}: {e}") from e

        self.cache[name] = data
        if len(self.cache) > self.max_cache:
            self.cache.popitem(last=False)

        return data

    def next_image_data(self) -> bytes:
        self.current_index += 1
        return self.get_image_data(self.current_index)


class ImagePreloader(QThread):
    image_ready = Signal(int, QPixmap)
    error_occurred = Signal(int, str)

    def __init__(self, comic: Comic, index: int) -> None:
        super().__init__()
        self.comic = comic
        self.index = index

    def run(self):
        try:
            data = self.comic.get_image_data(self.index)
        except Exception as e:
            self.error_occurred.emit(self.index, str(e))
            return None

        try:
            image = Image.open(BytesIO(data))
            image.load()
            image = image.convert("RGBA")

            qimage = QImage(
                image.tobytes("raw", "RGBA"),
                image.width,
                image.height,
                QImage.Format_RGBA8888,
            )
            pixmap = QPixmap.fromImage(qimage)

            self.image_ready.emit(self.index, pixmap)

        except Exception as e:
            self.error_occurred.emit(
                self.index, f"Error converting image at index {self.index}: {e}"
            )


class SimpleReader(QMainWindow):
    closed = Signal(str, int)

    def __init__(self, comic: Comic):
        super().__init__()
        self.comic = comic
        self.current_index: int = comic.current_index
        self._threads: list[ImagePreloader] = []
        self.image_cache: dict[int, QPixmap] = {}

        self.setWindowTitle("Comic Reader")

        self.image_label = QLabel("Loading...", alignment=Qt.AlignCenter)
        self.page_label = QLabel("Page 1", alignment=Qt.AlignCenter)

        self.menu_bar_widget = QWidget()
        self.menu_bar_layout = QHBoxLayout()
        self.menu_bar_widget.setLayout(self.menu_bar_layout)
        self.setMenuWidget(self.menu_bar_widget)

        self.add_menu_button("Navigation Toolbar", self.show_navigation_toolbar)
        self.add_menu_button("Comments Toolbar", self.show_comments_toolbar)
        self.add_menu_button("Metadata", self.open_metadata_panel)
        # self.add_menu_button("Settings", self.open_settings_panel)
        # self.add_menu_button("Help", self.open_help_panel)

        self.menu_bar_widget.hide()
        self.hide_menu_timer = QTimer()
        self.hide_menu_timer.setSingleShot(True)
        self.hide_menu_timer.timeout.connect(self.menu_bar_widget.hide)

        self.setMouseTracking(True)

        self.navigation_toolbar = QToolBar("Navigation Tools")
        self.navigation_toolbar.addAction("Zoom In")
        self.navigation_toolbar.addAction("Zoom Out")
        self.navigation_toolbar.addAction("Prev Page", self.prev_page)
        self.navigation_toolbar.addAction("Next Page", self.next_page)

        self.comments_toolbar = QToolBar("Commenting Tools")
        self.comments_toolbar.addAction("Add Bookmark")
        self.comments_toolbar.addAction("Add Comment")

        self.addToolBar(self.navigation_toolbar)
        self.addToolBar(self.comments_toolbar)

        self.navigation_toolbar.show()
        self.comments_toolbar.hide()
        self.current_toolbar = self.navigation_toolbar

        self.image_label.setFocusPolicy(Qt.StrongFocus)
        self.setCentralWidget(self.image_label)

        self.display_current_page()

    def preload_page(self, index: int, show_when_ready: bool = False) -> None:
        if index < 0 or index >= self.comic.total_pages:
            return
        if index in self.image_cache:
            if show_when_ready and index == self.current_index:
                self.render_pixmap(index, self.image_cache[index])
                return
        thread = ImagePreloader(self.comic, index)
        thread.image_ready.connect(
            lambda idx, pixmap: self.handle_preloaded_page(idx, pixmap, show_when_ready)
        )
        thread.finished.connect(lambda: self.cleanup_thread(thread))
        self._threads.append(thread)
        thread.start()

    def display_current_page(self) -> None:
        index = self.current_index
        print(index)
        if index in self.image_cache:
            pixmap = self.image_cache[index]
            self.render_pixmap(index, pixmap)
        else:
            self.preload_page(index, show_when_ready=True)

        # scaled = pixmap.scaledToHeight(
        #     self.image_label.height(), Qt.SmoothTransformation
        # )
        # self.image_label.setPixmap(scaled)
        # self.page_label.setText(f"Page {index + 1} / {self.comic.total_pages}")

        # if index + 1 < self.comic.total_pages:
        #     self.preload_page(index + 1)

    def handle_preloaded_page(self, index: int, pixmap: QPixmap, show: bool) -> None:
        self.image_cache[index] = pixmap

        if show and index == self.current_index:
            self.render_pixmap(index, pixmap)

    def render_pixmap(self, index: int, pixmap: QPixmap) -> None:
        scaled = pixmap.scaledToHeight(
            self.image_label.height(), Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)
        self.page_label.setText(f"Page {index + 1} / {self.comic.total_pages}")

        self.preload_surrounding_pages()

    def preload_surrounding_pages(self) -> None:
        for offset in [-2, -1, 1, 2]:
            index = self.current_index + offset
            if index not in self.image_cache:
                self.preload_page(index)

    def cleanup_thread(self, thread: ImagePreloader):
        if thread in self._threads:
            self._threads.remove(thread)
            thread.deleteLater()

    def add_menu_button(self, name: str, callback, *args):
        button = QToolButton()
        button.setText(name)
        button.setAutoRaise(True)
        button.clicked.connect(partial(callback, *args))
        self.menu_bar_layout.addWidget(button)

    def switch_toolbar(self, toolbar: QToolBar):
        if self.current_toolbar == toolbar:
            return
        self.current_toolbar.hide()
        toolbar.show()
        self.current_toolbar = toolbar

    def show_navigation_toolbar(self):
        self.switch_toolbar(self.navigation_toolbar)

    def show_comments_toolbar(self):
        self.switch_toolbar(self.comments_toolbar)

    def open_metadata_panel(self):
        self.metadata_popup = MetadataDialog(self.comic.info)
        self.metadata_popup.show()

    def resizeEvent(self, event):
        self.preload_page(self.current_index)

    def next_page(self):
        if self.current_index + 1 < self.comic.total_pages:
            self.current_index += 1
            self.display_current_page()

    def prev_page(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.display_current_page()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Right:
            self.next_page()
        elif key == Qt.Key_Left:
            self.prev_page()

    def mouseMoveEvent(self, event):
        mouse_y = event.position().y()

        if mouse_y <= 40:
            if not self.menu_bar_widget.isVisible():
                self.menu_bar_widget.show()
            self.hide_menu_timer.stop()

        else:
            if self.menu_bar_widget.isVisible() and not self.hide_menu_timer.isActive():
                self.hide_menu_timer.start(1500)
        super().mouseMoveEvent(event)

    def closeEvent(self, event) -> None:
        self.save_progress()
        event.accept()

    def save_progress(self):
        page = self.current_index
        with RepoWorker("D://adams-comics//.covers") as page_saver:
            if page == 0:
                return None
            elif page == self.comic.total_pages:
                page_saver.mark_as_finished(self.comic.id, page)
                return None
            page_saver.save_last_page(self.comic.id, page)

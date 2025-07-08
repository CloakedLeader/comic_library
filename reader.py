import os
import re
import sys
import zipfile
from collections import OrderedDict
from functools import partial
from io import BytesIO

from PIL import Image
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMainWindow,
                               QToolBar, QToolButton, QWidget)

# from metadata_gui_panel import MetadataDialog
from file_utils import get_name


def sort_imgs(filename: str) -> int | None:
    numbers = re.findall(r"\d+", filename)
    return int(numbers[-1]) if numbers else -1


class ComicError(Exception):
    """Base exception for Comic-related issues."""


class PageIndexError(ComicError):
    """Raised when a page index is out of range."""


class ImageLoadError(ComicError):
    """Raised when an image fails to load."""


class Comic:

    def __init__(self, filepath: str, max_cache: int = 10) -> None:
        self.path = filepath
        self.filename = get_name(filepath)
        self.zip = zipfile.ZipFile(filepath, "r")
        self.image_names = sorted(
            name for name in self.zip.namelist()
            if name.lower().endswith((".jpg", ".jpeg", ".png"))
        )
        if not self.image_names:
            raise ComicError("No images found in the file.")
        self.total_pages = self.total_pages()
        self.size = os.path.getsize(filepath)
        self.cache: OrderedDict[str, bytes] = OrderedDict()
        self.max_cache = max_cache
        self.current_index = 0

    def total_pages(self) -> int:
        return len(self.image_names)

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
        if len(self.cache) > self.max_cache_size:
            self.cache.popitem(last=False)

        return data

    def next_image_data(self) -> bytes:
        self.current_index += 1
        return self.get_image_data(self.current_index)


class ImagePreloader(QThread):
    image_ready = Signal(int, QPixmap)

    def __init__(self, comic: Comic, index: int):
        super().__init__()
        self.comic = comic
        self.index = index

    def run(self):
        data = self.comic.get_image_data(self.index)

        try:
            image = Image.open(BytesIO(data))
            image.load()
            image = image.convert("RGBA")

            qimage = QImage(
                image.tobytes("raw", "RGBA"),
                image.width,
                image.height,
                QImage.Format_RGBA8888
            )
            pixmap = QPixmap.fromImage(qimage)

            self.image_ready.emit(self.index, pixmap)
       
        except Exception as e:
            raise ImageLoadError(f"Error converting image at index {self.index}: {e}")


class SimpleReader(QMainWindow):
    def __init__(self, comic: Comic):
        super().__init__()
        self.comic = comic
        self.current_index = 0
        self._threads: list[ImagePreloader] = []

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
        self.image_label.setFocusPolicy(Qt.StrongFocus)

        self.preload_page(self.current_index)

    def preload_page(self, index: int) -> None:
        try:
            thread = ImagePreloader(self.comic, index)
            thread.image_ready.connect(self.display_page)
            thread.finished.connect(lambda: self.cleanup_thread(thread))
            self._threads.append(threads)
            thread.run()
        except PageIndexError as e:
            print(f"Invalid page index: {e}")
        
    def display_page(self, index: int, pixmap: QPixmap) -> None:
        if index != self.current_index:
            raise PageIndexError(f"Reader and page loader not in sync")
        
        scaled = pixmap.scaledToHeight(self.image_label.height(), Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)
        self.page_label.setText(f"Page {index + 1} / {self.comic.total_pages}")

        if index + 1 < self.comic.total_pages:
            self.preload_page(index + 1)

    def cleanup_thread(self, thread):
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
        print("Not yet implemented.")
        # dialog = MetadataDialog(self)
        # dialog.exec()

    def resizeEvent(self, event):
        self.load_page(self.current_index)

    def next_page(self):
        if self.current_index + 1 < self.reader.total_pages:
            self.current_index += 1
            self.preload_page(self.current_index)

    def prev_page(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.preload_pageload_page(self.current_index)

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    reader = Comic(
        r"""D://comic_library//comic_examples//Juggernaut -
    No Stopping Now TPB (March 2021).cbz"""
    )
    window = SimpleReader(reader)
    window.showMaximized()
    sys.exit(app.exec())

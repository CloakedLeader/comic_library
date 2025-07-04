import zipfile
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QMainWindow, QHBoxLayout,QHBoxLayout, QToolButton, QToolBar, QDialog
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, QThread, Signal, QTimer
import os
import sys
import re
from PIL import Image
from io import BytesIO
from collections import OrderedDict
from functools import partial

from metadata_gui_panel import MetadataDialog

def sort_imgs(filename: str) -> int | None:
    numbers = re.findall(r'\d+', filename)
    return int(numbers[-1]) if numbers else -1 

class ImagePreloader(QThread):
    image_ready = Signal(int, QPixmap)

    def __init__(self, reader, index):
        super().__init__()
        self.reader = reader
        self.index = index

    def run(self):
        pixmap = self.reader.load_page(self.index)
        if pixmap:
            self.image_ready.emit(self.index, pixmap)

class Comic: 
    def __init__( self, filepath: str, max_cache=10 ):
        self.path = filepath
        self.filename = os.path.basename(filepath)
        self.zip = zipfile.ZipFile(filepath, 'r')
        self.image_names = sorted(
            [name for name in self.zip.namelist() if name.lower().endswith((".jpg", ".jpeg", ".png"))]
        )
        self.size = os.path.getsize(filepath)
        self.page_counter = 1
        self.cache = OrderedDict()
        self.max_cache_size = max_cache


    def load_page(self, index):
        if index < 0 or index >= len(self.image_names):
            return None
        name = self.image_names[index -1]
        if name in self.cache:
            self.cache.move_to_end(name)
            return self.cache[name]
        try:
            with self.zip.open(name) as file:
                image = Image.open(BytesIO(file.read()))
                image.load()

                data = image.convert("RGBA").tobytes("raw", "RGBA")
                qimage = QImage(data, image.width, image.height, QImage.Format_RGBA8888)
                pixmap = QPixmap.fromImage(qimage)

                self.cache[name] = pixmap
                if len(self.cache) > self.max_cache_size:
                    self.cache.popitem(last=False)  # Remove LRU
                return pixmap
        except Exception as e:
            print(f"Failed to load image {name}: {e}")
            return None

    def total_pages(self):
        return len(self.image_names)
    

    def get_page( self, number: int):
        if number < 0 or number >= len(self.image_names):
            return None
        name = self.image_names[number - 1]
        if name not in self.cache:
            with self.zip.open(name) as file:
                image_data = file.read()
                image = Image.open(BytesIO(image_data))
                image.load()
                self.cache[name] = image
        return self.cache[name]

    def next_page( self ):
        self.page_counter += 1
        self.get_page( self.page_counter )


class SimpleReader(QMainWindow):
    def __init__(self, reader: Comic):
        super().__init__()
        self.reader = reader
        self.current_index = 1
        self._threads = []

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
        #self.add_menu_button("Settings", self.open_settings_panel)
        #self.add_menu_button("Help", self.open_help_panel)

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
        
        # self.toolbar_stack = QStackedWidget()
        # self.toolbar_stack.addWidget(self.navigation_toolbar)
        # self.toolbar_stack.addWidget(self.comments_toolbar)

        self.addToolBar(self.navigation_toolbar)
        self.addToolBar(self.comments_toolbar)

        self.navigation_toolbar.show()
        self.comments_toolbar.hide()
        self.current_toolbar = self.navigation_toolbar

        self.image_label.setFocusPolicy(Qt.StrongFocus)

        self.setCentralWidget(self.image_label)
        self.centralWidget().setMouseTracking(True)

        self.load_page(self.current_index)

    def load_page(self, index):
        pixmap = self.reader.load_page(index)
        if pixmap:
            
            scaled = pixmap.scaledToHeight(self.image_label.height(), Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)
            self.page_label.setText(f"Page {index + 1} / {self.reader.total_pages()}")
            self.current_index = index

            # Preload next page
            if index + 1 < self.reader.total_pages():
                thread = ImagePreloader(self.reader, index + 1)
                thread.image_ready.connect(lambda i, p: print(f"Preloaded page {i}"))
                self._threads.append(thread)
                thread.start()

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
        dialog = MetadataDialog(self.reader)
        dialog.exec()


    def resizeEvent(self, event):
        self.load_page(self.current_index)

    def next_page(self):
        if self.current_index + 1 < self.reader.total_pages():
            self.load_page(self.current_index + 1)

    def prev_page(self):
        if self.current_index > 0:
            self.load_page(self.current_index - 1)

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
    reader = Comic(r"D://comic_library//comic_examples//Juggernaut - No Stopping Now TPB (March 2021).cbz")
    window = SimpleReader(reader)
    window.showMaximized()
    sys.exit(app.exec())

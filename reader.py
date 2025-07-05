import zipfile
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QMainWindow, QHBoxLayout,QHBoxLayout, QSpacerItem, QSizePolicy
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, QThread, Signal
import os
import sys
import re
from PIL import Image
from io import BytesIO
from collections import OrderedDict

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

tester_comic = Comic(r"comic_pwa/comic_folder/wildcats v1 047 (1998) 22p [image].cbz")


class SimpleReader(QMainWindow):
    def __init__(self, reader):
        super().__init__()
        self.reader = reader
        self.current_index = 1
        self._threads = []

        self.setStyleSheet("background-color: #9a9594; colour: white;")

        self.setWindowTitle("Comic Reader")
        self.resize(800, 1000)

        self.image_label = QLabel("Loading...", alignment=Qt.AlignCenter)
        self.page_label = QLabel("Page 1", alignment=Qt.AlignCenter)

        self.prev_button = QPushButton("Previous")
        self.next_button = QPushButton("Next")

        self.prev_button.setFocusPolicy(Qt.NoFocus)
        self.next_button.setFocusPolicy(Qt.NoFocus)

        self.prev_button.clicked.connect(self.prev_page)
        self.next_button.clicked.connect(self.next_page)

        self.bookmark_button = QPushButton("Bookmark")
        self.settings_button = QPushButton("Settings")
        self.help_button = QPushButton("Help")

        top_button_layout = QHBoxLayout()
        top_button_layout.addWidget(self.bookmark_button)
        top_button_layout.addWidget(self.settings_button)
        top_button_layout.addWidget(self.help_button)
        top_button_layout.addWidget(self.prev_button)
        top_button_layout.addWidget(self.next_button)
        top_button_layout.addStretch()

        self.bookmark_button.setFocusPolicy(Qt.NoFocus)
        self.settings_button.setFocusPolicy(Qt.NoFocus)
        self.help_button.setFocusPolicy(Qt.NoFocus)

        layout = QVBoxLayout()
        layout.addLayout(top_button_layout)
        layout.addWidget(self.image_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

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




    # def __init__(self):
    #     super().__init__()
    #     self.setWindowTitle("Image Viewer")

    #     self.comic = tester_comic

    #     # Main layout
    #     main_widget = QWidget()
    #     self.setCentralWidget(main_widget)

    #     self.vbox = QVBoxLayout()
    #     main_widget.setLayout(self.vbox)

    #     # Image display
    #     self.label = QLabel()
    #     self.vbox.addWidget(self.label)

    #     # Navigation buttons
    #     hbox = QHBoxLayout()
    #     self.prev_button = QPushButton("← Previous")
    #     self.next_button = QPushButton("Next →")
    #     hbox.addWidget(self.prev_button)
    #     hbox.addWidget(self.next_button)
    #     self.vbox.addLayout(hbox)

    #     self.prev_button.clicked.connect(self.show_previous_page)
    #     self.next_button.clicked.connect(self.show_next_page)

    #     self.update_image()

    # def update_image(self):
    #     if 1 <= self.comic.page_counter:
    #         pixmap = QPixmap()
    #         pixmap.loadFromData(self.comic.get_page(self.comic.page_counter))
    #         self.label.setPixmap(pixmap)
    #         self.resize(pixmap.width(), pixmap.height() + 50)  # Extra space for buttons

    # def show_next_page(self):
    #     self.comic.page_counter += 1
    #     self.update_image()

    # def show_previous_page(self):
    #     if self.comic.page_counter > 1:
    #         self.comic.page_counter -= 1
    #         self.update_image()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    reader = Comic(r"D://comic_library//Juggernaut - No Stopping Now TPB (March 2021).cbz")
    window = SimpleReader(reader)
    window.showMaximized()
    sys.exit(app.exec())

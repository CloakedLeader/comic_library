import sys
import os
import os.path
from io import BytesIO
from typing import Tuple

from PySide6.QtWidgets import QMainWindow, QToolBar, QApplication, QHBoxLayout, QLineEdit, QWidget, QVBoxLayout, QSizePolicy, QScrollArea, QLabel, QTreeView, QStatusBar
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFileSystemModel
import requests

from download_controller import DownloadControllerAsync, DownloadServiceAsync
from reader_controller import ReadingController
from rss_controller import RSSController
from rss_repository import RSSRepository

class ClickableComicWidget(QWidget):
    clicked = Signal()

    def __init__(self, title: str, pixmap: QPixmap, img_width=20, img_height=20, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        cover_label = QLabel()
        cover_label.setPixmap(pixmap.scaled(img_width, img_height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        cover_label.setAlignment(Qt.AlignCenter)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)

        layout.addWidget(cover_label)
        layout.addWidget(title_label)

        self.setStyleSheet("""
            ComicButton {
                border: 1px solid #aaa;
                border-radius: 4px;
                background-color: #f9f9f9;
            }
            ComicButton:hover {
                background-color: #e6f7ff;
            }
        """)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

class HomePage(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Comic Library Homepage")

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction("Browse..")
        menu_bar.addMenu("Settings")
        menu_bar.addMenu("Help")

        toolbar = QToolBar("Metadata")
        self.addToolBar(toolbar)
        toolbar.addAction("Edit")
        toolbar.addAction("Retag")

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search comics..")
        self.search_bar.setFixedWidth(200)
        toolbar.addWidget(self.search_bar)

        self.status = QStatusBar()
        self.setStatusBar(self.status)


        body_layout = QHBoxLayout()
        body_widget = QWidget()
        body_widget.setLayout(body_layout)


        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(os.path.expanduser("D://Comics//Marvel"))
        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setRootIndex(self.file_model.index(os.path.expanduser("D://Comics//Marvel")))
        self.file_tree.setMaximumWidth(200)
        self.file_tree.setHeaderHidden(True)

        for i in range(1, self.file_model.columnCount()):
            self.file_tree.hideColumn(i)

        body_layout.addWidget(self.file_tree, stretch=1)
        
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)

        stats_bar = self.create_stats_bar()
        #stats_bar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        #stats_bar.setMaximumHeight(70)
        continue_reading = self.create_continue_reading_area(dummy_data)
        #recommended = self.create_recommended_reading_area()
        need_review = self.create_review_area(dummy_data)
        rss = self.create_rss_area()

        content_layout.addWidget(stats_bar)
        content_layout.addWidget(continue_reading)
        content_layout.addWidget(need_review)
        content_layout.addWidget(rss)
        body_layout.addWidget(content_area)

        self.setCentralWidget(body_widget)
    
    def load_pixmap_from_url(self, url: str) -> QPixmap:
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

    def create_scroll_area(self, list_of_dicts: list, header: str, upon_clicked, links=False) -> QScrollArea:
        img_width, img_height = 120, 180

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        container = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(16)
        container.setLayout(layout)

        title = QLabel(f"{header}")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")

        for comic in list_of_dicts:

            if links:
                pixmap = self.load_pixmap_from_url(comic["cover_link"])

            else:
                pixmap = QPixmap(comic["cover_path"])

            title_name = comic.get("title")
            comic_button = ClickableComicWidget(title_name, pixmap, img_width, img_height)
            comic_button.clicked.connect(lambda c=comic: upon_clicked(c))

            layout.addWidget(comic_button)

        final_layout = QVBoxLayout()
        final_widget = QWidget()
        final_widget.setLayout(final_layout)
        final_layout.addWidget(title)
        final_layout.addWidget(container)    

        scroll_area.setWidget(final_widget)
        return scroll_area

    def open_reader(self, comic: dict):
        cont = ReadingController(comic)
        cont.read_comic()
        
    def print_hi(self):
        print("Hi")

    def create_continue_reading_area(self, list_of_comics_marked_as_read):
        return self.create_scroll_area(list_of_comics_marked_as_read, header="Continue Reading", upon_clicked=self.open_reader)
    
    def create_recommended_reading_area(self, list_of_recommended_comics):
        return self.create_scroll_area(list_of_recommended_comics, header="Recommended Next Read", upon_clicked=self.open_reader)
    
    def create_review_area(self, list_of_unreviewed_comics):
        return self.create_scroll_area(list_of_unreviewed_comics, header="Write a review...", upon_clicked=self.print_hi)
    
    def create_rss_area(self):
        repository = RSSRepository("comics.db")
        rss_cont = RSSController(repository)
        recent_comics_list = rss_cont.run(6)
        self.rss_controller = DownloadControllerAsync(view=self, service=DownloadServiceAsync())
        return self.create_scroll_area(recent_comics_list, links=True, header="GetComics RSS Feed", upon_clicked=self.rss_controller.handle_rss_comic_clicked)
        
    def create_stats_bar(self):
        files_num, storage_val = count_files_and_storage("D:\\Comics\\Marvel")

        def create_stat_widget(title: str, image_path: str, value: str) -> QWidget:
            widget = QWidget()
            layout = QVBoxLayout()
            #layout.setSpacing(2)
            #layout.setContentsMargins(0,0,0,0)
            layout.setAlignment(Qt.AlignCenter)
            widget.setLayout(layout)

            title_label = QLabel(title)
            title_label.setAlignment(Qt.AlignCenter)

            pixmap = QPixmap(image_path)
            image_label = QLabel()
            image_label.setPixmap(pixmap.scaled(50,50,Qt.KeepAspectRatio, Qt.SmoothTransformation))
            image_label.setAlignment(Qt.AlignCenter)

            value_label = QLabel(value)
            value_label.setAlignment(Qt.AlignCenter)

            layout.addWidget(title_label)
            layout.addWidget(image_label)
            layout.addWidget(value_label)

            return widget

        stats = QWidget()
        layout = QHBoxLayout(stats)

        layout.addWidget(create_stat_widget("Number of Comics",
                                            "D:\\comic_library\\comic_gui\\comicbook.png",
                                            str(files_num)))
        
        layout.addWidget(create_stat_widget("Storage", 
                                            "D:\\comic_library\\comic_gui\\storage.png",
                                            f"{round(storage_val, 2)} GB"))

        final_widget = QWidget()
        final_layout = QVBoxLayout()
        #final_layout.setSpacing(3)
        #final_layout.setContentsMargins(0,0,0,0)
        final_widget.setLayout(final_layout)
        title = QLabel("Your Statistics")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 12px; font-weight: bold; padding: 2px;")
        final_layout.addWidget(title)
        final_layout.addWidget(stats)

        return final_widget

    def update_status(self, message: str):
        self.status.showMessage(message, 4000)

def count_files_and_storage(directory: str) -> tuple[int, float]:
    total_size = 0
    file_count = 0
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                file_count += 1
                total_size += os.path.getsize(fp)
    total_size = total_size / (1024**3)
    return file_count, total_size

dummy_data = [{"title": "Mr Miracle TPB", "cover_path" : "D:\\Comics\\.yacreaderlibrary\\covers\\1f7c63fb2bf06fcd4293fad5928354e591542fb9459630961.jpg", "filepath": "D://Comics//DC//Misc//Mister Miracle TPB (February 2019).cbz"}, 
              {"title" : "Daredevil: The Man Witout Fear", "cover_path" : "D:\\Comics\\.yacreaderlibrary\\covers\\051a70f024954f92e2b2c0699f00859ac772e865685497443.jpg"}]


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HomePage()
    window.show()
    sys.exit(app.exec())

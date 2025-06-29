from PySide6.QtWidgets import QMainWindow, QToolBar, QApplication, QHBoxLayout, QLineEdit, QWidget, QVBoxLayout, QSizePolicy, QScrollArea, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
import sys
import os
import os.path
from typing import Tuple

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

        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)

        stats_bar = self.create_stats_bar()
        continue_reading = self.create_continue_reading_area(dummy_data)
        #recommended = self.create_recommended_reading_area()
        #rss = self.create_rss_area()

        content_layout.addWidget(stats_bar)
        content_layout.addWidget(continue_reading)
        self.setCentralWidget(content_area)
    
    def create_scroll_area(self, list_of_dicts: list) -> QScrollArea:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        container = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(16)
        container.setLayout(layout)

        for comic in list_of_dicts:
            comic_widget = QWidget()
            comic_layout = QVBoxLayout()
            comic_layout.setAlignment(Qt.AlignCenter)
            comic_widget.setLayout(comic_layout)

            pixmap = QPixmap(comic["cover_path"])
            cover_label = QLabel()
            cover_label.setPixmap(pixmap.scaled(120, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            cover_label.setAlignment(Qt.AlignCenter)

            title_label = QLabel(comic["title"])
            title_label.setAlignment(Qt.AlignCenter)
            title_label.setWordWrap(True)

            comic_layout.addWidget(cover_label)
            comic_layout.addWidget(title_label)

            layout.addWidget(comic_widget)
        
        scroll_area.setWidget(container)
        return scroll_area

    def create_continue_reading_area(self, list_of_comics_marked_as_read):
        return self.create_scroll_area(list_of_comics_marked_as_read)
    
    def create_recommended_reading_area(self, list_of_recommended_comics):
        pass


    def create_stats_bar(self):
        files_num, storage_val = count_files_and_storage("D:\\Comics\\Marvel")

        def create_stat_widget(title: str, image_path: str, value: str) -> QWidget:
            widget = QWidget()
            layout = QVBoxLayout()
            layout.setAlignment(Qt.AlignCenter)
            widget.setLayout(layout)

            title_label = QLabel(title)
            title_label.setAlignment(Qt.AlignCenter)

            pixmap = QPixmap(image_path)
            image_label = QLabel()
            image_label.setPixmap(pixmap.scaled(80,120,Qt.KeepAspectRatio, Qt.SmoothTransformation))
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

        return stats



    def search(self, query: str):
        pass

def count_files_and_storage(dir: str) -> Tuple[int, float]:
    total_size = 0
    file_count = 0
    for dirpath, _, filenames in os.walk(dir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                file_count += 1
                total_size += os.path.getsize(fp)
    total_size = total_size / (1024**3)
    return file_count, total_size


dummy_data = [{"title": "Mr Miracle TPB", "cover_path" : "D:\\Comics\\.yacreaderlibrary\\covers\\1f7c63fb2bf06fcd4293fad5928354e591542fb9459630961.jpg"}, 
              {"title" : "Daredevil: The Man Witout Fear", "cover_path" : "D:\\Comics\\.yacreaderlibrary\\covers\\051a70f024954f92e2b2c0699f00859ac772e865685497443.jpg"}]



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HomePage()
    window.show()
    sys.exit(app.exec())

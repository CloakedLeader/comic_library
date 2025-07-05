from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout, QScrollArea, QApplication, QMainWindow, QTreeView, QLineEdit, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QFileSystemModel
import sys
import os
from pathlib import Path


class ComicLibraryUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Comic Library Manager")
        self.setMinimumSize(1000, 700)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        top_bar = QHBoxLayout()
        top_bar.addStretch()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search comics...")
        self.search_bar.setFixedWidth(200)
        top_bar.addWidget(self.search_bar)

        top_bar_widget = QWidget()
        top_bar_widget.setLayout(top_bar)
        main_layout.addWidget(top_bar_widget)

        body_layout = QHBoxLayout()
        body_widget = QWidget()
        body_widget.setLayout(body_layout)
        main_layout.addWidget(body_widget)

        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(os.path.expanduser(r"D:\Comics\Marvel"))
        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setRootIndex(self.file_model.index(os.path.expanduser(r"D:\Comics\Marvel")))
        self.file_tree.setColumnWidth(0, 200)
        self.file_tree.setHeaderHidden(True)

        body_layout.addWidget(self.file_tree, stretch=1)

        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)


        stats_bar = self.create_stats_bar()
        continue_reading = self.create_scroll_bar("Continue Reading")
        recommended = self.create_scroll_bar("Recommended")
        rss_downloads = self.create_scroll_bar("Available to Download")

        content_layout.addWidget(stats_bar)
        content_layout.addWidget(continue_reading)
        content_layout.addWidget(recommended)
        content_layout.addWidget(rss_downloads)

        body_layout.addWidget(content_area, stretch=3)

    def create_stats_bar(self):
        stats = QWidget()
        layout = QHBoxLayout()
        stats.setLayout(layout)

        layout.addWidget(QLabel(f"Comics: {count_files("D:\\Comics\\Marvel")}"))
        layout.addWidget(QLabel("Read: 75"))
        layout.addWidget(QLabel("Unread: 75"))
        layout.addWidget(QLabel(f"Total Size: {size_directory("D:\\Comics\\Marvel")}GB"))

        return stats

    def create_scroll_bar(self, title):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        container = QWidget()
        layout = QHBoxLayout()
        container.setLayout(layout)

        for i in range(8):
            layout.addWidget(QLabel(f"{title} {i+1}"))
        
        scroll_area.setWidget(container)
        return scroll_area
    

def count_files(directory):
        path = Path(directory)
        if not path.exists():
             print(f"Directory does not exist: {directory}")
             return 0
        return sum(1 for file in path.glob('*') if file.is_file())
    

def size_directory(directory):
     return int((sum(f.stat().st_size for f in Path(directory).rglob("*") if f.is_file())/1e9))
    

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ComicLibraryUI()
    window.show()
    sys.exit(app.exec())

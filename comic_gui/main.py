from PySide6.QtWidgets import QMainWindow, QToolBar, QApplication, QHBoxLayout, QLineEdit, QWidget, QVBoxLayout, QSizePolicy
import sys

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
        self.search_bar.setFixedWidth(150)
        toolbar.addWidget(self.search_bar)

    def search(self, query: str):
        pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HomePage()
    window.show()
    sys.exit(app.exec())

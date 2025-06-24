import sys
from PySide6.QtWidgets import QApplication, QMainWindow
from comic_gui.home_page import HomePage

app = QApplication(sys.argv)
window = QMainWindow()
home = HomePage()
window.setCentralWidget(home)
window.resize(500, 400)
window.show()
app.exec()
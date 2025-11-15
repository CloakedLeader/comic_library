from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class StyledButton(QWidget):
    clicked = Signal(int)
    doubleClicked = Signal()

    def __init__(self, name: str, primary_key: int, parent=None):
        super().__init__(parent)
        self.key = primary_key
        self.setAttribute(Qt.WA_StyledBackground, True)

        style_sheet = """
            #comicCard {
                background-color: #f0f0f0;

                border: 1px solid #ccc;

                border-radius: 6px;
                padding: 8px;
            }
            #comicCard:hover {

                background-color: #f5f5f5;
            }
            """

        self.button_layout = QHBoxLayout()
        self.button_layout.addWidget(QLabel(name))

        self.setObjectName("comicCard")
        self.setStyleSheet(style_sheet)
        self.setLayout(self.button_layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.key)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit()


class ButtonDisplay(QWidget):
    def __init__(
        self,
        header: str,
        titles: list[str],
        ids: list[int],
        left_clicked: Callable,
    ):
        super().__init__()

        layout = QVBoxLayout()
        layout.setSpacing(4)
        container = QWidget()
        container.setLayout(layout)

        label = QLabel(header)
        label.setStyleSheet("font: bold 12px;")
        layout.addWidget(label)

        combined = list(zip(titles, ids))

        for title, id in combined:
            widget = StyledButton(title, id, self)
            widget.clicked.connect(left_clicked)
            widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            layout.addWidget(widget)

        self.setLayout(layout)

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reader import SimpleReader

class MetadataDialog(QDialog):
    def __init__(self, reader: SimpleReader) -> None:
        super().__init__()
        self.setWindowTitle(f"Metadata for {reader.filename}")

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Here you will see all the different metadata fields."))

        close_button = QPushButton()
        close_button.setText("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        self.setLayout(layout)

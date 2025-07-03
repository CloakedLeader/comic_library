from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton

class MetadataDialog(QDialog):
    def __init__(self, reader):
        super().__init__()
        self.setWindowTitle(f"Metadata for {reader.filename}")

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Here you will see all the different metadata fields."))

        close_button = QPushButton()
        close_button.setText("Close this useless window.")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.setLayout(layout)



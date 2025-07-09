from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

from reader import Comic


class MetadataDialog(QDialog):
    """
    A dialog window for displaying comic metadata information.
    """

    def __init__(self, comic: Comic) -> None:
        """
        Initialise the metadata dialog.

        Args:
            comic: A Comic instance containing comic data and filename.

        This dialog shows metadata fields for a given comic reader instance
        and provides a close button for user interaction.
        """
        super().__init__()
        self.setWindowTitle(f"Metadata for {comic.filename}")

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Here you will see all the different metadata fields."))

        close_button = QPushButton()
        close_button.setText("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        self.setLayout(layout)

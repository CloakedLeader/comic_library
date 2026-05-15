"""
A popup window for creating a comic collection by entering a name.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database.gui_repo_worker import RepoWorker


class CollectionCreation(QDialog):
    """
    A dialog window for asking the user to create and name a comic collection.

    An empty entry is not allowed and will lead to an error message.
    """

    def __init__(self) -> None:
        """
        Creates the dialog window with a QTextBox to enter the collection
        title.
        """
        super().__init__()

        self.main_display = QWidget()
        self.main_layout = QVBoxLayout(self.main_display)

        prompt = QLabel("Enter collection title:")
        self.textbox = QLineEdit()
        self.textbox.setPlaceholderText("Collection..")
        self.main_layout.addWidget(prompt)
        self.main_layout.addWidget(self.textbox)

        self.create_coll = QPushButton("Create collection")
        self.create_coll.clicked.connect(self.create_collection)
        self.exit_button = QPushButton("Cancel")
        self.exit_button.clicked.connect(self.reject)
        button_holder = QWidget()
        button_layout = QHBoxLayout(button_holder)
        button_layout.addWidget(self.create_coll)
        button_layout.addWidget(self.exit_button)
        self.main_layout.addWidget(button_holder)

        self.setLayout(self.main_layout)

    def create_collection(self) -> None:
        """
        Creates an entry in the database with the collection name.
        If the entry is empty ("") then an error message is shown
        so that user either exits or inputs a non-empty
        string.
        """
        name = self.textbox.text()
        if name == "":
            self.error_message("Cannot have empty name.").exec()
        else:
            with RepoWorker() as worker:
                worker.create_collection(name)
            self.accept()

    @staticmethod
    def error_message(message: str) -> QDialog:
        """
        Creates an error message QDialog box. This will pop up
        as the front-most widget and the UI cannot be used
        until it is dismissed.

        Args:
            message (str): The message to display in the popup.

        Returns:
            QDialog: The QDialog box to display.
        """
        error_dialog = QDialog()
        error_dialog.setWindowTitle("Error!")
        message_box = QLabel(message)
        layout = QVBoxLayout(error_dialog)
        layout.addWidget(message_box)
        exit_button = QPushButton("Ok")
        layout.addWidget(exit_button, alignment=Qt.AlignmentFlag.AlignBottom)
        exit_button.clicked.connect(error_dialog.close)
        return error_dialog

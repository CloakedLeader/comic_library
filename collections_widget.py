from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout, QWidget)

from database.gui_repo_worker import RepoWorker


class CollectionCreation(QDialog):
    def __init__(self):
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

    def create_collection(self):
        name = self.textbox.text()
        with RepoWorker() as worker:
            worker.create_collection(name)
        self.accept()

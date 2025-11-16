import os

from dotenv import load_dotenv, set_key
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QVBoxLayout, QWidget)

ENV_PATH = ".env"


class Settings(QDialog):
    def __init__(self):
        super().__init__()

        self.main_display = QWidget()
        self.main_layout = QVBoxLayout(self.main_display)

        self.main_layout.addWidget(QLabel("Enter your API key:"))
        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("Your API key..")
        self.main_layout.addWidget(self.api_input)

        self.main_layout.addWidget(
            QLabel("Select the parent directory for your comics:")
        )
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("No folder selected")
        self.main_layout.addWidget(self.path_input)
        browse = QPushButton("Browse")
        browse.clicked.connect(self.browse_folder)
        self.main_layout.addWidget(browse)

        button_display = QWidget()
        button_holder = QHBoxLayout(button_display)
        self.exit = QPushButton("Cancel")
        self.exit.clicked.connect(self.reject)
        self.apply = QPushButton("Apply")
        self.apply.clicked.connect(self.save_env_vars)
        self.okay_button = QPushButton("Ok")
        self.okay_button.clicked.connect(self.okay_pressed)
        button_holder.addWidget(self.exit, 1)
        button_holder.addWidget(QWidget(), 2)
        right_holder = QHBoxLayout()
        right_widget = QWidget()
        right_widget.setLayout(right_holder)
        right_holder.addWidget(self.apply)
        right_holder.addWidget(self.okay_button)
        button_holder.addWidget(right_widget, 1)

        self.main_layout.addWidget(button_display)
        self.setLayout(self.main_layout)

        self.key, self.dir = self.load_vars()

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.path_input.setText(folder)

    def load_vars(self):
        if os.path.exists(ENV_PATH):
            load_dotenv(ENV_PATH)
            current_key = os.getenv("API_KEY", "")
            current_dir = os.getenv("ROOT_DIR", "")
            if current_key != "":
                self.api_input.setText(current_key)
            if current_dir != "":
                self.path_input.setText(current_dir)
        else:
            current_dir = ""
            current_key = ""

        return current_key, current_dir

    def save_env_vars(self):
        api_key = self.api_input.text().strip()
        folder = self.path_input.text().strip()
        if not os.path.exists(ENV_PATH):
            with open(ENV_PATH, "w") as f:
                f.write("")

        set_key(ENV_PATH, "API_KEY", api_key)
        set_key(ENV_PATH, "ROOT_DIR", folder)
        load_dotenv(ENV_PATH, override=True)

    def okay_pressed(self):
        if (
            self.api_input.text().strip() != self.key
            or self.path_input.text().strip() != self.dir
        ):
            self.unsaved_changes = SaveChanges()
            result = self.unsaved_changes.exec()

            if result == QDialog.DialogCode.Accepted:
                self.save_env_vars()
                self.accept()

            elif result == QDialog.DialogCode.Rejected:
                self.api_input.setText(self.key)
                self.path_input.setText(self.dir)
                self.accept()


class SaveChanges(QDialog):
    def __init__(self):
        super().__init__()

        self.main_display = QWidget()
        self.main_layout = QVBoxLayout(self.main_display)

        self.main_layout.addWidget(QLabel("You have unsaved changes."))
        self.save_and_quit = QPushButton("Save and Quit")
        self.discard_changes = QPushButton("Discard Changes")
        self.main_layout.addWidget(self.save_and_quit)
        self.main_layout.addWidget(self.discard_changes)
        self.save_and_quit.clicked.connect(self.accept)
        self.discard_changes.clicked.connect(self.reject)

        self.setLayout(self.main_layout)

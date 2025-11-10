from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QApplication,
)
import os
from dotenv import load_dotenv, set_key

ENV_PATH = ".env"


class Settings(QWidget):
    def __init__(self):
        super().__init__()

        self.main_display = QWidget()
        self.main_layout = QVBoxLayout(self.main_display)

        self.main_layout.addWidget(QLabel("Enter your API key:"))
        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("Your API key..")
        self.main_layout.addWidget(self.api_input)

        self.main_layout.addWidget(QLabel("Select the parent directory for your comics:"))
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("No folder selected")
        self.main_layout.addWidget(self.path_input)
        browse = QPushButton("Browse")
        browse.clicked.connect(self.browse_folder)
        self.main_layout.addWidget(browse)

        button_display = QWidget()
        button_holder = QHBoxLayout(button_display)
        self.exit = QPushButton("Cancel")
        self.apply = QPushButton("Apply")
        self.done = QPushButton("Ok")
        button_holder.addWidget(self.exit, 1)
        button_holder.addWidget(QWidget(), 2)
        right_holder = QHBoxLayout()
        right_widget = QWidget()
        right_widget.setLayout(right_holder)
        right_holder.addWidget(self.apply)
        right_holder.addWidget(self.done)
        button_holder.addWidget(right_widget, 1)

        self.main_layout.addWidget(button_display)
        self.setLayout(self.main_layout)

        self.load_vars()

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
    
    def save_env_vars(self):
        api_key = self.api_input.text().strip()
        folder = self.path_input.text().strip()
        if not os.path.exists(ENV_PATH):
            with open(ENV_PATH, "w") as f:
                f.write("")
        
        set_key(ENV_PATH, "API_KEY", api_key)
        set_key(ENV_PATH, "ROOT_DIR", folder)
        load_dotenv(ENV_PATH, override=True)


if __name__ == "__main__":
    app = QApplication([])
    window = Settings()
    window.show()
    app.exec()

    







        




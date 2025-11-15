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


class ReadingOrderCreation(QDialog):
    def __init__(self):
        super().__init__()

        self.main_display = QWidget()
        self.main_layout = QVBoxLayout(self.main_display)

        prompt = QLabel("Enter order title:")
        self.textbox = QLineEdit()
        self.textbox.setPlaceholderText("Reading Order..")
        self.main_layout.addWidget(prompt)
        self.main_layout.addWidget(self.textbox)
        prompt2 = QLabel("Add a description:")
        self.textbox2 = QLineEdit()
        self.textbox2.setPlaceholderText("Description..")
        self.main_layout.addWidget(prompt2)
        self.main_layout.addWidget(self.textbox2)

        self.create_coll = QPushButton("Create order")
        self.create_coll.clicked.connect(self.create_order)
        self.exit_button = QPushButton("Cancel")
        self.exit_button.clicked.connect(self.reject)
        button_holder = QWidget()
        button_layout = QHBoxLayout(button_holder)
        button_layout.addWidget(self.create_coll)
        button_layout.addWidget(self.exit_button)
        self.main_layout.addWidget(button_holder)

        self.setLayout(self.main_layout)

    def create_order(self):
        name = self.textbox.text()
        description = self.textbox2.text()

        with RepoWorker() as worker:
            if description == "":
                description = None
            worker.create_reading_order(name, description)
        
        self.open_order_creation()

    def open_order_creation(self):
        pass


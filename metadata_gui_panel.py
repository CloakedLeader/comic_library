from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui_repo_worker import RepoWorker
from helper_classes import GUIComicInfo


class DashboardBox(QGroupBox):
    def __init__(self, title):
        super().__init__(title)
        layout = QVBoxLayout()
        self.setLayout(layout)

    def add_role_box(self, role_box: QWidget):
        self.layout().addWidget(role_box)

    def add_content(self, content):
        label = QLabel(content)
        label.setAlignment(Qt.AlignCenter)
        self.layout().addWidget(label)


class RoleBox(QGroupBox):
    def __init__(self, role_title: str, people_list: list[str]):
        super().__init__()
        layout = QVBoxLayout()

        title_label = QLabel(role_title)
        title_label.setStyleSheet("font-weight: bold; font-size: 14pt;")
        layout.addWidget(title_label)

        for person in people_list:
            person_label = QLabel(person)
            layout.addWidget(person_label)

        self.setLayout(layout)


class MetadataDialog(QMainWindow):
    """
    A dialog window for displaying comic metadata information.
    """

    def __init__(self, comic_data: GUIComicInfo) -> None:
        """
        Initialise the metadata dialog.

        Args:
            comic: A Comic instance containing comic data and filename.

        This dialog shows metadata fields for a given comic reader instance
        and provides a close button for user interaction.
        """
        self.primary_id = comic_data.primary_id
        self.coverpath = comic_data.cover_path
        self.filepath = comic_data.filepath
        with RepoWorker("D://adams-comics//.covers") as info_getter:
            metadata = info_getter.get_complete_metadata(self.primary_id)
        super().__init__()
        self.setWindowTitle(f"Metadata for {metadata.name}")
        self.setMinimumSize(800, 600)

        main_layout = QVBoxLayout()
        content_layout = QGridLayout()

        creators_box = DashboardBox("Creators")
        for role, people in metadata.creators:
            creators_box.add_role_box(RoleBox(role, people))

        description_box = DashboardBox("Description")
        description_box.add_content(metadata.description)

        thumbnail_filename = f"{self.primary_id}_t.jpg"
        thumbnail_pix = QPixmap("D://adams-comics//.covers//" + thumbnail_filename)
        thumbnail_label = QLabel()
        thumbnail_label.setPixmap(thumbnail_pix)
        thumbnail_label.setScaledContents(False)
        thumbnail_label.adjustSize()
        title_cover_box = QVBoxLayout()
        title_cover_widget = QWidget()
        title_cover_widget.setLayout(title_cover_box)
        title_cover_box.addWidget(thumbnail_label)
        title_cover_box.addWidget(QLabel(metadata.name))

        stars = self.make_star_rating(rating=metadata.rating)

        content_layout.addWidget(title_cover_widget, 0, 0, 1, 1)
        content_layout.addWidget(creators_box, 1, 0, -1, 1)
        content_layout.addWidget(description_box, 0, 1, 1, 2)
        content_layout.addWidget(stars, 0, 3, 1, 1)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)

        content_widget = QWidget()
        content_widget.setLayout(content_layout)

        main_layout.addWidget(content_widget)
        main_layout.addWidget(close_button, alignment=Qt.AlignRight)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def make_star_rating(self, rating: float, max_stars=5) -> QLabel:
        full_star = "★"
        empty_star = "☆"
        stars = ""

        filled = int(rating)
        for i in range(max_stars):
            if i < filled:
                stars += f"""
                <span style="color: gold; font-size: 20pt;">{full_star}</span>"""
            else:
                stars += f"""
                <span style="color: lightgray; font-size: 20pt;">{empty_star}</span>"""

        label = QLabel()
        label.setText(stars)
        label.setTextFormat(Qt.RichText)
        return label

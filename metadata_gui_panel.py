import re
from textwrap import dedent

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui_repo_worker import RepoWorker
from helper_classes import GUIComicInfo, MetadataInfo


class DashboardBox(QGroupBox):
    def __init__(self, title, wrap: bool = False):
        super().__init__(title)
        self.wrap = wrap
        layout = QVBoxLayout()
        self.setLayout(layout)

    def add_role_box(self, role_box: QWidget):
        self.layout().addWidget(role_box)

    def add_content(self, content):
        label = QLabel(content)
        label.setWordWrap(self.wrap)
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

        description_box = DashboardBox("Description", True)
        clean_desc = metadata.description.translate(str.maketrans("", "", "\n\t\r"))
        description_box.add_content(clean_desc)

        review_container = QWidget()
        review_layout = QVBoxLayout()
        review_container.setLayout(review_layout)
        button_container = QWidget()
        button_layout = QHBoxLayout()
        button_container.setLayout(button_layout)
        current_review = QWidget()
        current_review_layout = QVBoxLayout()
        current_review.setLayout(current_review_layout)
        self.text_edit = QTextEdit()
        review_area = QScrollArea()
        self.text_edit.setPlaceholderText("Write your review here...")
        if len(metadata.reviews) != 0:
            for review, date, iteration in metadata.reviews:
                if not review:
                    continue
                preset_text = dedent(
                    f"""
                    <u>Review No. {iteration} Date: {date}</u><br>
                    {review}<br><br>
                """
                )
                review_layout.addWidget(QLabel(preset_text))

        save_button = QPushButton("Save")
        undo_button = QPushButton("Undo")
        undo_button.clicked.connect(self.text_edit.undo)
        save_button.clicked.connect(self.save_current_review)
        button_layout.addWidget(save_button)
        button_layout.addWidget(undo_button)
        current_review_layout.addWidget(button_container, stretch=1)
        current_review_layout.addWidget(self.text_edit, stretch=5)
        review_layout.addWidget(current_review)
        review_area.setWidget(review_container)
        review_area.setWidgetResizable(True)

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
        content_layout.addWidget(review_area, 1, 1, 1, 2)

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

        if not rating:
            empty_star_str = f"""
            <span style="color: lightgray; font-size: 20pt;">{empty_star}</span>"""
            for _ in range(5):
                stars += empty_star_str
        else:
            filled = int(rating / 2)
            for i in range(max_stars):
                if i < filled:
                    stars += f"""
                    <span style="color: gold; font-size: 20pt;">{full_star}</span>"""
                else:
                    stars += f"""
                    <span style="color: lightgray; font-size: 20pt;">
                    {empty_star}</span>"""

        label = QLabel()
        label.setText(stars)
        label.setTextFormat(Qt.RichText)
        return label

    def save_current_review(self) -> None:
        current_text = self.text_edit.toPlainText()
        with RepoWorker("D://adams-comics//.covers") as review_saver:
            review_saver.input_review_column(
                primary_key=self.primary_id, review_text=current_text
            )
        return None


class MetadataPanel(QWidget):
    def __init__(self, comic_metadata: MetadataInfo):
        super().__init__()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        quick_icons = QWidget()
        quick_icons_layout = QHBoxLayout(quick_icons)
        quick_icons_layout.setContentsMargins(10, 10, 10, 10)
        quick_icons_layout.setSpacing(10)

        read_status = QLabel("Read" if comic_metadata.reviews else "Unread")
        read_status.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        quick_icons_layout.addWidget(read_status)

        liked_box = QCheckBox("Liked")
        liked_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        quick_icons_layout.addWidget(liked_box)

        rating = int(comic_metadata.rating / 2) if comic_metadata.rating else 0
        full_star = "★"
        empty_star = "☆"
        stars = ""
        for i in range(5):
            if i < rating:
                stars += f"""
                <span style="color: gold; font-size: 20pt;">{full_star}</span>"""
            else:
                stars += f"""
                <span style="color: lightgray; font-size: 20pt;">{empty_star}</span>"""
        stars_label = QLabel(stars)
        stars_label.setTextFormat(Qt.RichText)
        stars_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        quick_icons_layout.addWidget(stars_label)

        layout.addWidget(quick_icons)

        display_text = f"#{comic_metadata.volume_num} - {comic_metadata.name}"
        title_widget = QLabel(display_text)
        title_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(title_widget)

        formatted_desc = comic_metadata.description or ""
        clean_desc = re.sub(r"\s+", " ", formatted_desc).strip()
        desc_widget = QLabel(clean_desc)
        desc_widget.setWordWrap(True)
        desc_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout.addWidget(desc_widget)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setLayout(layout)

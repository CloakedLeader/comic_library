"""
A user-oriented panel for displaying comic metadata and user interactions
such as reviews, comments and rating.
"""

import os
import re
from pathlib import Path
from textwrap import dedent

from dotenv import load_dotenv
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from classes.helper_classes import GUIComicInfo, MetadataInfo
from database.gui_repo_worker import RepoWorker

load_dotenv()
root_folder = os.getenv("ROOT_DIR")
ROOT_DIR = Path(root_folder if root_folder is not None else "")

TITLE_STYLE = """
QLabel {
    color: #888888;
    font-size: 12px;
}"""

INFORMATION_STYLE = """
QLabel {
    color: #1a1a1a;
    font-size: 14px;
}"""


class DashboardBox(QGroupBox):
    """
    A reusable vertical layout for adding elements inside to display.

    Attributes:

        box_layout (QVBoxLayout): The box layout to add sub-widgets.
        wrap (bool): Whether to have the text in the boxes wrap.
    """

    def __init__(self, title: str, wrap: bool = False):
        """
        Creates the box with a title at the top and a vertical layout within.

        Args:
            title (_type_): The title for the display box.
            wrap (bool, optional): Whether to have the text wrap around and under.
            Defaults to False.
        """
        super().__init__(title)
        self.wrap = wrap
        self.box_layout = QVBoxLayout()
        self.setLayout(self.box_layout)

    def add_role_box(self, role_box: QWidget):
        """Adds a pre-existing widget to the layout."""
        self.box_layout.addWidget(role_box)

    def add_content(self, content):
        """
        Adds any type of content to the layout.

        Supports:
            - QWidget -> added directly
            - QLayout -> added as a sub-layout
            - Other -> converted to QLabel
        """
        if isinstance(content, QWidget):
            self.box_layout.addWidget(content)
            return

        if isinstance(content, QLayout):
            self.box_layout.addLayout(content)
            return

        label = QLabel(content)
        label.setWordWrap(self.wrap)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.box_layout.addWidget(label)

    def addLayout(self, layout: QLayout):
        self.box_layout.addLayout(layout)


class RoleBox(QGroupBox):
    """
    A reusable box for creating one box for each createor for the metadata panel.
    """

    def __init__(self, role_title: str, people_list: list[str]):
        """
        Creates a box with the role name as the title and then the names underneath.

        Args:
            role_title (str): The role the box is for. Is the title of the box.
            people_list (list[str]): The people to include in the box.
        """
        super().__init__()
        layout = QVBoxLayout()

        self.is_empty = len(people_list) == 0
        if len(people_list) == 1 and people_list[0] in ("MISSING", "<MISSING>"):
            self.is_empty = True

        title_label = QLabel(role_title)
        title_label.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title_label)
        if len(people_list) > 2:
            grid = QGridLayout()
            grid_index = 0
            for _, person in enumerate(people_list):
                if person in ("MISSING", "<MISSING>"):
                    continue
                row = grid_index // 2
                col = grid_index % 2
                person_label = QLabel(person)
                person_label.setStyleSheet(INFORMATION_STYLE)
                grid.addWidget(person_label, row, col)
                grid_index += 1

            layout.addLayout(grid)
        else:
            for person in people_list:
                if person in ("MISSING", "<MISSING>"):
                    continue
                person_label = QLabel(person)
                person_label.setStyleSheet(INFORMATION_STYLE)
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
        with RepoWorker() as info_getter:
            metadata = info_getter.get_complete_metadata(self.primary_id)
        super().__init__()
        self.setWindowTitle(f"Metadata for {metadata.title}: {metadata.series}")
        self.setMinimumSize(800, 600)
        self.name = f"{metadata.series}: {metadata.title}"

        main_layout = QVBoxLayout()
        content_layout = QGridLayout()

        creators_box = DashboardBox("Creators")
        for role, people in metadata.creators:
            box = RoleBox(role, people)
            if box.is_empty:
                continue
            creators_box.add_role_box(box)

        description_box = DashboardBox("Description", True)
        clean_desc = re.sub(r"\n\s*\n", "<br><br>", metadata.description).strip()
        # clean_desc = metadata.description.translate(str.maketrans("", "", "\n\t\r"))
        description_box.add_content(clean_desc)

        review_container = QWidget()
        review_layout = QVBoxLayout(review_container)
        review_container.setLayout(review_layout)
        button_container = QWidget()
        button_layout = QHBoxLayout()
        button_container.setLayout(button_layout)
        current_review = QWidget()
        current_review_layout = QVBoxLayout()
        current_review.setLayout(current_review_layout)
        self.text_edit = QTextEdit()
        review_area = QScrollArea()
        review_area.setStyleSheet("QScrollArea { border: none; }")
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
        review_panel = DashboardBox("Reviews", wrap=False)
        review_panel.add_content(review_area)

        thumbnail_filename = f"{self.primary_id}_t.jpg"
        thumbnail_pix = QPixmap(ROOT_DIR / ".covers" / thumbnail_filename)
        thumbnail_label = QLabel()
        thumbnail_label.setPixmap(thumbnail_pix)
        thumbnail_label.setScaledContents(False)
        thumbnail_label.adjustSize()
        title_cover_box = QVBoxLayout()
        title_cover_widget = QWidget()
        title_cover_widget.setLayout(title_cover_box)
        title_cover_box.addWidget(thumbnail_label)

        stars = self.make_star_rating(rating=metadata.rating if metadata.rating else 0)

        title_cover_box.addWidget(self.create_overview_widget(metadata, stars))
        overview_panel = DashboardBox("Overview", wrap=False)
        overview_panel.add_content(title_cover_widget)

        content_layout.addWidget(overview_panel, 0, 0, 3, 1)
        content_layout.addWidget(creators_box, 2, 3, 2, 1)
        content_layout.addWidget(description_box, 0, 1, 2, 2)
        # content_layout.addWidget(stars, 0, 3, 1, 1)
        content_layout.addWidget(review_panel, 2, 1, 2, 2)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)

        content_widget = QWidget()
        content_widget.setLayout(content_layout)

        main_layout.addWidget(content_widget)
        main_layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def make_star_rating(self, rating: float, max_stars=5) -> QLabel:
        """
        Displays the number of stars depending on the rating.

        Returns:
            QLabel: A widget with the text that are the correct number of stars.
        """
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
        label.setTextFormat(Qt.TextFormat.RichText)
        return label

    def save_current_review(self) -> None:
        """Saves the currently written review to the database."""
        current_text = self.text_edit.toPlainText()
        with RepoWorker() as review_saver:
            review_saver.input_review_column(
                primary_key=self.primary_id, review_text=current_text
            )
        return None

    def create_overview_widget(self, metadata: MetadataInfo, stars: QLabel) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        series_title = QLabel("Series")
        series_title.setStyleSheet(TITLE_STYLE)
        series_content = QLabel(metadata.series)
        series_content.setStyleSheet(INFORMATION_STYLE)
        layout.addWidget(series_title)
        layout.addWidget(series_content)

        title_title = QLabel("Title/Book")
        title_title.setStyleSheet(TITLE_STYLE)
        title_content = QLabel(metadata.title)
        title_content.setStyleSheet(INFORMATION_STYLE)
        layout.addWidget(title_title)
        layout.addWidget(title_content)

        volume_title = QLabel("Volume")
        volume_title.setStyleSheet(TITLE_STYLE)
        volume_content = QLabel(f"Volume {metadata.volume_num}")
        volume_content.setStyleSheet(INFORMATION_STYLE)
        layout.addWidget(volume_title)
        layout.addWidget(volume_content)

        publisher_title = QLabel("Publisher")
        publisher_title.setStyleSheet(TITLE_STYLE)
        publisher_content = QLabel(metadata.publisher)
        publisher_content.setStyleSheet(INFORMATION_STYLE)
        layout.addWidget(publisher_title)
        layout.addWidget(publisher_content)

        date_title = QLabel("Date")
        date_title.setStyleSheet(TITLE_STYLE)
        date_content = QLabel(metadata.date)
        date_content.setStyleSheet(INFORMATION_STYLE)
        layout.addWidget(date_title)
        layout.addWidget(date_content)

        layout.addWidget(stars)
        layout.addWidget(QLabel("FAVOURITE BUTTON COMING SOON!"))
        return widget


class MetadataPanel(QWidget):
    """
    The metadata panel that appears on the right when a comic is clicked.
    """

    def __init__(self, comic_metadata: MetadataInfo):
        """
        Creates the widget to be displayed with all the information and layout.

        Args:
            comic_metadata (MetadataInfo): The complete metadata for the comic.
        """
        super().__init__()
        self.name = f"{comic_metadata.title}: {comic_metadata.series}"
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        quick_icons = QWidget()
        quick_icons_layout = QHBoxLayout(quick_icons)
        quick_icons_layout.setContentsMargins(10, 10, 10, 10)
        quick_icons_layout.setSpacing(10)

        read_status = QLabel("Read" if comic_metadata.reviews else "Unread")
        read_status.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        quick_icons_layout.addWidget(read_status)

        liked_box = QCheckBox("Liked")
        liked_box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
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
        stars_label.setTextFormat(Qt.TextFormat.RichText)
        stars_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        quick_icons_layout.addWidget(stars_label)

        layout.addWidget(quick_icons)

        display_text = f"#{comic_metadata.volume_num} - {self.name}"
        title_widget = QLabel(display_text)
        title_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(title_widget)

        formatted_desc = comic_metadata.description or ""
        clean_desc = re.sub(r"\s+", " ", formatted_desc).strip()
        desc_widget = QLabel(clean_desc)
        desc_widget.setWordWrap(True)
        desc_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(desc_widget)

        total_creator_info = ""
        for role, creators_list in comic_metadata.creators:
            filtered_creators = [
                c for c in creators_list if c not in ("MISSING", "<MISSING>")
            ][:5]
            if role not in ["Editor", "Letterer", "Inker"]:
                if len(filtered_creators) == 0:
                    continue
                temp_string = f"{role}: "
                temp_string += ", ".join(filtered_creators)
                temp_string += "\n"
                total_creator_info += temp_string
        creator_widget = QLabel(total_creator_info)
        creator_widget.setWordWrap(True)
        layout.addWidget(creator_widget)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setLayout(layout)

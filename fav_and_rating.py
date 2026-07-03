""" "
A collection of widgets for user interactivity with the comics.

Includes a favourite button shaped as a heart, and a rating system with stars.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

load_dotenv()
resources_path = os.getenv("FRONTEND_RESOURCES")
IMAGES = Path((resources_path or ""))


class HeartButton(QPushButton):
    """
    A heart shaped button for the user to show that the comic is a favourite.

    When clicked the heart turns red, with an animation to be added later.
    """

    def __init__(self, already_fav: bool, size: tuple[int, int]):
        """
        Intialises the heart button in the the correct form, checked or unchecked
        depending on the `already_fav` argument.

        Args:
            already_fav (bool): Whether the comic was already flagged as a favourite
                and is stored in the database.
            size (tuple[int, int]): The base size of the widget in the form
                `(width, height)`.
        """
        super().__init__()
        self.setCheckable(True)
        self.base_size = QSize(size[0], size[1])
        self.empty_icon = QIcon(str(IMAGES / "heart_outline.svg"))
        self.full_icon = QIcon(str(IMAGES / "heart_filled.svg"))

        self.toggled.connect(self.update_icon)
        self.setIcon(self.empty_icon)
        self.setChecked(already_fav)

        self.setFixedSize(self.base_size)
        self.setIconSize(self.size())
        self.setStyleSheet("QPushButton { border: none; }")

    def update_icon(self, checked: bool):
        """
        Change the icon of the button when clicked.

        Args:
            checked (bool): Whether the button is checked or unchecked.
        """
        self.setIcon(self.full_icon if checked else self.empty_icon)


class StarRating(QWidget):
    """
    A clickable widget containing 5 stars which can have their fill adjusted to match
    the required rating for the comic.
    """

    def __init__(self, rating: float, size: tuple[int, int]):
        """
        Creates the empty stars and then fills them to the required level using the
        `rating` argument.

        Args:
            rating (float): The comic rating as a float, it is a number between 0 and 5.0
                in increments of 0.5.
            size (tuple[int, int]): The base size of the widget in the form
                `(width, height)`.
        """
        super().__init__()
        self.rating = rating
        self.base_width = size[0]
        self.base_height = size[1]
        self.stars: list[QLabel] = []
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.full_star = QPixmap(str(IMAGES / "star_filled.svg"))
        self.half_star = QPixmap(str(IMAGES / "star_half.svg"))
        self.empty_star = QPixmap(str(IMAGES / "star_outline.svg"))

        layout = QHBoxLayout(self)
        self.spacing = 2
        layout.setSpacing(self.spacing)
        layout.setContentsMargins(0, 0, 0, 0)

        for _ in range(5):
            label = QLabel()
            label.setFixedSize(self.base_width, self.base_height)
            label.setScaledContents(True)
            self.stars.append(label)
            layout.addWidget(label)

        self.update_stars()

    def sizeHint(self):
        """Gives the size hint to callers including spacing to maintain widget size."""
        width = 5 * self.base_width + 4 * self.spacing
        return QSize(width, self.base_height)

    def minimumSizeHint(self):
        """Provides the minimum widget size to callers."""
        return self.sizeHint()

    def update_stars(self):
        """Updates the star rating depening on the instance attribute `self.rating`."""
        for i, star in enumerate(self.stars):
            if self.rating >= i + 1:
                star.setPixmap(self.full_star)
            elif self.rating >= i + 0.5:
                star.setPixmap(self.half_star)
            else:
                star.setPixmap(self.empty_star)

    def mousePressEvent(self, event):
        """
        Detects the position of a mouse click and updates the star rating to the correct
        position.
        """
        x = event.position().toPoint()

        for i, star in enumerate(self.stars):
            if star.geometry().contains(x):
                local_x = x.x() - star.x()

                if local_x < star.width() / 2:
                    self.rating = i + 0.5
                else:
                    self.rating = i + 1.0
        self.update_stars()
        return super().mousePressEvent(event)

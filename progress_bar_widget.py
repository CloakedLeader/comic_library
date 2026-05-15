"""
Creates the assets for the reading progress bar.
"""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget


class CoverWithProgress(QWidget):
    """
    Comic cover image object with a reading progress bar painted over it.

    Takes the standard cover image and uses :class `QPaint` to add a bar
    at the bottom signifying the reading progress.
    """

    def __init__(self, image_path: str, progress: float, parent=None):
        """
        Intialises the cover image widget.

        Args:
            image_path (str): The filepath to the comic cover.
            progress (float): The current reading progress as a decimal (0.0 < x < 1.0).
            parent (_type_, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.pixmap = QPixmap(image_path)
        self.progress = progress

        self.setMinimumSize(250, 400)
        self.setMaximumSize(250, 400)

    def set_progress(self, value):
        """
        Sets the reading progress to edit the widget in place.
        Then updates the view.

        Args:
            value (_type_): The new reading progress decimal.
        """
        self.progress = max(0.0, min(1.0, value))
        self.update()

    def paintEvent(self, event):
        """
        Paints over the comic cover image with a green bar at the bottom
        which represents the reading progress.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        painter.drawPixmap(self.rect(), self.pixmap)

        bar_height = 10
        bar_width = int(self.width() * self.progress)
        bar_rect = QRect(0, self.height() - bar_height, bar_width, bar_height)

        painter.setBrush(QColor(80, 80, 80, 180))
        painter.setPen(Qt.NoPen)  # type: ignore
        painter.drawRect(0, self.height() - bar_height, self.width(), bar_height)

        painter.setBrush(QColor(0, 200, 0, 200))
        painter.drawRect(bar_rect)

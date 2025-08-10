from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget


class CoverWithProgress(QWidget):
    def __init__(self, image_path: str, progress: float, parent=None):
        super().__init__(parent)
        self.pixmap = QPixmap(image_path)
        self.progress = progress

        self.setMinimumSize(250, 400)
        self.setMaximumSize(250, 400)

    def set_progress(self, value):
        self.progress = max(0.0, min(1.0, value))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        painter.drawPixmap(self.rect(), self.pixmap)

        bar_height = 10
        bar_width = int(self.width() * self.progress)
        bar_rect = QRect(0, self.height() - bar_height, bar_width, bar_height)

        painter.setBrush(QColor(80, 80, 80, 180))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, self.height() - bar_height, self.width(), bar_height)

        painter.setBrush(QColor(0, 200, 0, 200))
        painter.drawRect(bar_rect)

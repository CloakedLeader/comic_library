from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget


class HeartButton(QPushButton):
    def __init__(self, already_fav: bool):
        super().__init__()
        self.setCheckable(True)

        self.empty_icon = QIcon("gui_resources/heart_outline.svg")
        self.full_icon = QIcon("gui_resources/heart_filled.svg")

        if not already_fav:
            self.setIcon(self.empty_icon)
        else:
            self.setIcon(self.full_icon)
        self.setFixedSize(30, 30)
        self.setIconSize(self.size())
        self.toggled.connect(self.update_icon)
        self.setStyleSheet("QPushButton { border: none; }")

    def update_icon(self, checked):
        self.setIcon(self.full_icon if checked else self.empty_icon)


class StarRating(QWidget):
    def __init__(self, rating: float):
        super().__init__()
        self.rating = rating
        self.stars: list[QLabel] = []
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.full_star = QPixmap("gui_resources/star_filled.svg")
        self.half_star = QPixmap("gui_resources/star_half.svg")
        self.empty_star = QPixmap("gui_resources/star_outline.svg")

        layout = QHBoxLayout(self)
        self.spacing = 2
        layout.setSpacing(self.spacing)
        layout.setContentsMargins(0, 0, 0, 0)

        for _ in range(5):
            label = QLabel()
            label.setFixedSize(30, 30)
            label.setScaledContents(True)
            self.stars.append(label)
            layout.addWidget(label)

        self.update_stars()

    def sizeHint(self):
        width = 5 * 30 + 4 * self.spacing
        return QSize(width, 30)

    def minimumSizeHint(self):
        return self.sizeHint()

    def update_stars(self):
        for i, star in enumerate(self.stars):
            if self.rating >= i + 1:
                star.setPixmap(self.full_star)
            elif self.rating >= i + 0.5:
                star.setPixmap(self.half_star)
            else:
                star.setPixmap(self.empty_star)

    def mousePressEvent(self, event):
        x = event.position().toPoint()

        for i, star in enumerate(self.stars):
            if star.geometry().contains(x):
                local_x = x.x() - star.x()

                if local_x < star.width() / 2:
                    self.rating = i + 0.5
                else:
                    self.rating = i + 1.0
        print(self.rating)
        self.update_stars()
        return super().mousePressEvent(event)

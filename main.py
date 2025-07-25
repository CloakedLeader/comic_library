import os
import os.path
import sys
from io import BytesIO
from typing import Callable

import requests
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileSystemModel,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QScrollArea,
    QSizePolicy,
    QStatusBar,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from reader_controller import ReadingController
from rss_controller import RSSController
from rss_repository import RSSRepository
from gui_repo_worker import RepoWorker
from helper_classes import GUIComicInfo


class ClickableComicWidget(QWidget):
    """
    A clickable widget for displaying comic information with
    cover and title.

    This widget displays a comic cover image and title in a vertical
    layout and emits a clicked signal when the user clicks on it.

    Signals:
        clicked: Emitted when the widget is clicked with the left mouse button.
    """

    clicked = Signal()

    def __init__(
        self,
        title: str,
        pixmap: QPixmap,
        img_width=20,
        img_height=20,
        parent: QWidget | None = None,
    ) -> None:
        """
        Intialise the clickable comic widget.

        Args:
            title: The comic title to display.
            pixmap: The cover image as a QPixmap.
            img_width: Width to scale the cover image to.
            img_height: Height to scale the cover image to.
            Parent: Parent widget to embed it in, optional.
        """
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        cover_label = QLabel()
        cover_label.setPixmap(
            pixmap.scaled(
                img_width, img_height, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )
        cover_label.setAlignment(Qt.AlignCenter)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)

        layout.addWidget(cover_label)
        layout.addWidget(title_label)

        self.setStyleSheet(
            """
            ComicButton {
                border: 1px solid #aaa;
                border-radius: 4px;
                background-color: #f9f9f9;
            }
            ComicButton:hover {
                background-color: #e6f7ff;
            }
        """
        )

    def mousePressEvent(self, event) -> None:
        """
        Handle mouse press events to emit clicked signal.

        Args:
            event: The mouse press event.
        """
        if event.button() == Qt.LeftButton:
            self.clicked.emit()


class HomePage(QMainWindow):
    """
    Main window for the Comic Library application.

    This class provides the primary user interface for browsing comics,
    including file system navigation, RSS feed integration, reading
    recommendations and download management.
    Features include:
        - File system tree view for comic browsing
        - Multiple scrollable sections for different comic categories
        - RSS feed integration for new comic discovery
    """

    def __init__(self) -> None:
        """
        Initalise the homepage main window.

        Sets up a complete UI including menu bar, toolbar, status bar, file
        system view, content area and RSS feed integration.
        """
        super().__init__()
        self.setWindowTitle("Comic Library Homepage")

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction("Browse..")
        menu_bar.addMenu("Settings")
        menu_bar.addMenu("Help")

        toolbar = QToolBar("Metadata")
        self.addToolBar(toolbar)
        toolbar.addAction("Edit")
        toolbar.addAction("Retag")

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search comics..")
        self.search_bar.setFixedWidth(200)
        toolbar.addWidget(self.search_bar)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        body_layout = QHBoxLayout()
        body_widget = QWidget()
        body_widget.setLayout(body_layout)

        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(os.path.expanduser("D://adams-comics"))
        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setRootIndex(
            self.file_model.index(os.path.expanduser("D://adams-comics"))
        )
        self.file_tree.setMaximumWidth(200)
        self.file_tree.setHeaderHidden(True)

        for i in range(1, self.file_model.columnCount()):
            self.file_tree.hideColumn(i)

        body_layout.addWidget(self.file_tree, stretch=1)

        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)

        with RepoWorker("D://adams-comics//.covers") as repo:
            continue_list, review_list = repo.run()

        stats_bar = self.create_stats_bar()
        stats_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        stats_bar.setMaximumHeight(60)
        continue_reading = self.create_continue_reading_area(continue_list)
        # recommended = self.create_recommended_reading_area()
        need_review = self.create_review_area(review_list)
        # rss = self.create_rss_area(12)

        content_layout.addWidget(stats_bar, stretch=1)
        content_layout.addWidget(continue_reading, stretch=3)
        content_layout.addWidget(need_review, stretch=3)
        # content_layout.addWidget(rss, stretch=3)
        body_layout.addWidget(content_area, stretch=1)

        self.setCentralWidget(body_widget)

    def load_pixmap_from_url(self, url: str) -> QPixmap:
        """
        Loads a QPixmap from a URL with error handling.

        Args:
            url: The URL image of the image to load.

        Returns:
            The loaded image or a gray placeholder if loading fails.

        Downloads the image from the given URL and converts it to
        a QPixmap. Returns a 120x180 gray placeholder if the
        download fails.
        """
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            image_data = BytesIO(response.content)
            pixmap = QPixmap()
            if pixmap.loadFromData(image_data.read()):
                return pixmap
        except Exception as e:
            print(f"Failed to load image from {url}: {e}")
        fallback = QPixmap(120, 180)
        fallback.fill(Qt.gray)
        return fallback

    def create_scroll_area(
        self,
        list_of_dicts: list[GUIComicInfo],
        header: str,
        upon_clicked: Callable,
        links: bool = False,
    ) -> QScrollArea:
        """
        Create a horizontal scroll area populated with comic widgets.

        Args:
            list_of_dicts: List of dictionaries containing comic
        information.
            header: Text for the scroll area section title.
            upon_clicked: Callback function to execute when a
        comic is clicked.
        links: Whether the comics are from the RSS links.

        Returns:
            A configured QScrollArea with clickable comic widgets.

        Creates a scroll area with comic widgets arranged horizontally.
        Each comic displays a cover image and title, and connects to the
        provided callback function when clicked.
        """
        img_width, img_height = 120, 180

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        container = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(16)
        container.setLayout(layout)

        title = QLabel(f"{header}")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            """font-size: 18px;
                             font-weight: bold; padding: 10px;"""
        )

        for comic in list_of_dicts:

            if links and comic.cover_link is not None:
                pixmap = self.load_pixmap_from_url(comic.cover_link)

            else:
                pixmap = QPixmap(comic.cover_path)

            title_name = comic.title
            comic_button = ClickableComicWidget(
                title_name, pixmap, img_width, img_height
            )
            comic_button.clicked.connect(lambda c=comic: upon_clicked(c))

            layout.addWidget(comic_button)

        final_layout = QVBoxLayout()
        final_widget = QWidget()
        final_widget.setLayout(final_layout)
        final_layout.addWidget(title)
        final_layout.addWidget(container)

        scroll_area.setWidget(final_widget)
        return scroll_area

    def open_reader(self, comic: dict) -> None:
        """
        Open a comic reader for the specified comic.

        Args:
            Dictionary containing information about the comic
            including filepath and database id.
        """
        cont = ReadingController(comic)
        cont.read_comic()

    def print_hi(self, comic_dict: GUIComicInfo) -> None:
        print("Hi " + comic_dict.title + "!")

    def create_continue_reading_area(
        self, list_of_comics_marked_as_read: list[GUIComicInfo]
    ) -> QScrollArea:
        """
        Creates a scroll area for comics marked as continue reading.

        Args:
            list_of_comics_marked_as_read: List of comics to display.
        """
        return self.create_scroll_area(
            list_of_comics_marked_as_read,
            header="Continue Reading",
            upon_clicked=self.open_reader,
        )

    def create_recommended_reading_area(
        self, list_of_recommended_comics: list[GUIComicInfo]
    ) -> QScrollArea:
        """
        Creates a scroll area for comics marked as recommended.

        Args:
            list_of_recommended_comics: List of recommended
        comics to display.
        """
        return self.create_scroll_area(
            list_of_recommended_comics,
            header="Recommended Next Read",
            upon_clicked=self.open_reader,
        )

    def create_review_area(self, list_of_unreviewed_comics: list[GUIComicInfo]
                           ) -> QScrollArea:
        """
        Creates a scroll area for comics marked as requiring
        review.

        Args:
            list_of_unreviewed_comics: List of unreviewed comics
        to display.
        """
        return self.create_scroll_area(
            list_of_unreviewed_comics,
            header="Write a review...",
            upon_clicked=self.print_hi,
        )

    def create_rss_area(self, num: int = 8) -> QScrollArea:
        """
        Creates a scroll area for RSS feed comics.

        Fetches recent comics from the RSS controller and
        creates a scroll area with download functionality
        for each comic.
        """
        repository = RSSRepository("comics.db")
        rss_cont = RSSController(repository)
        recent_comics_list = rss_cont.run(num)
        # self.rss_controller = DownloadControllerAsync(
        #     view=self, service=DownloadServiceAsync()
        # )
        return self.create_scroll_area(
            recent_comics_list,
            links=True,
            header="GetComics RSS Feed",
            upon_clicked=self.print_hi,  # self.rss_controller.handle_rss_comic_clicked,
        )

    def create_stats_bar(self) -> QWidget:
        """
        Create and return a statistics bar widget.

        Returns:
            A QWidget containing comic library statistics.
        """
        files_num, storage_val = count_files_and_storage("D:\\adams-comics")

        def create_stat_widget(title: str, image_path: str, value: str) -> QWidget:
            """
            Create a single statistic widget.

            Args:
                title: The statistic title.
                image_path: Path to the icon image.
                value: The statistic value to display.

            Returns:
                A QWidget displaying the statistic with title, icon
            and value.
            """
            widget = QWidget()
            layout = QVBoxLayout()
            # layout.setSpacing(2)
            # layout.setContentsMargins(0,0,0,0)
            layout.setAlignment(Qt.AlignCenter)
            widget.setLayout(layout)

            title_label = QLabel(title)
            title_label.setAlignment(Qt.AlignCenter)

            pixmap = QPixmap(image_path)
            image_label = QLabel()
            image_label.setPixmap(
                pixmap.scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            image_label.setAlignment(Qt.AlignCenter)

            value_label = QLabel(value)
            value_label.setAlignment(Qt.AlignCenter)

            layout.addWidget(title_label)
            layout.addWidget(image_label)
            layout.addWidget(value_label)

            return widget

        stats = QWidget()
        layout = QHBoxLayout(stats)

        layout.addWidget(
            create_stat_widget(
                "Number of Comics",
                "D:\\comic_library\\comic_gui\\comicbook.png",
                str(files_num),
            )
        )

        layout.addWidget(
            create_stat_widget(
                "Storage",
                "D:\\comic_library\\comic_gui\\storage.png",
                f"{round(storage_val, 2)} GB",
            )
        )

        final_widget = QWidget()
        final_layout = QVBoxLayout()
        # final_layout.setSpacing(3)
        # final_layout.setContentsMargins(0,0,0,0)
        final_widget.setLayout(final_layout)
        title = QLabel("Your Statistics")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            """font-size: 12px;
                             font-weight: bold; padding: 2px;"""
        )
        final_layout.addWidget(title)
        final_layout.addWidget(stats)

        return final_widget

    def update_status(self, message: str) -> None:
        """
        Update the status bar with a message.

        Args:
            message: The message to display in the
        status bar.
        """
        self.status.showMessage(message, 4000)


def count_files_and_storage(directory: str) -> tuple[int, float]:
    """
    Count files and calculate total storage usage in a directory.

    Args:
        directory: Path to the parent directory containing the comics.

    Returns:
        A tuple containing (file_count, size_in_gb).

    Recursively walks through the directory structure, counting all files
    (excluding symbolic links) and calculating the total size in bytes. This
    is then converted to gigabytes.
    """
    total_size = 0.0
    file_count = 0
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                file_count += 1
                total_size += os.path.getsize(fp)
    total_size = total_size / (1024**3)
    return file_count, total_size


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HomePage()
    window.show()
    sys.exit(app.exec())

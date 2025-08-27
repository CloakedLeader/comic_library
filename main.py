import asyncio
import inspect
import os
import os.path
import sys
from io import BytesIO
from pathlib import Path
from typing import Callable, Optional

import requests
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileSystemModel,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from qasync import QEventLoop

from cleanup import scan_and_clean
from comic_grid_view import ComicGridView
from comic_match_ui import ComicMatcherUI
from download_controller import DownloadControllerAsync, DownloadServiceAsync
from database.gui_repo_worker import RepoWorker
from classes.helper_classes import GUIComicInfo, RSSComicInfo
from metadata_controller import run_tagger
from metadata_gui_panel import MetadataDialog, MetadataPanel
from reader_controller import ReadingController
from rss_controller import RSSController
from rss_repository import RSSRepository
from search import text_search


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
        # img_width=20,
        img_height=400,
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
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        cover_label = QLabel()
        cover_label.setAlignment(Qt.AlignCenter)
        cover_label.setFixedHeight(img_height)
        cover_label.setPixmap(
            pixmap.scaledToHeight(img_height, Qt.SmoothTransformation)
            # pixmap.scaled(
            #     img_width, img_height, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        cover_label.setSizePolicy(
            cover_label.sizePolicy().horizontalPolicy(), QSizePolicy.Fixed
        )
        cover_label.setToolTip(title)
        # title_label = QLabel(title)
        # title_label.setAlignment(Qt.AlignCenter)
        # title_label.setWordWrap(True)

        layout.addWidget(cover_label)
        # layout.addWidget(title_label)

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
        self.metadata_panel: Optional[MetadataPanel] = None
        self.setWindowTitle("Comic Library Homepage")

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction("Browse..")
        menu_bar.addMenu("Settings")
        menu_bar.addMenu("Help")

        toolbar = QToolBar("Metadata")
        self.addToolBar(toolbar)
        self.home_action = toolbar.addAction("Home")
        self.home_action.triggered.connect(self.go_home)
        self.home_action.setShortcut("Ctrl+H")
        self.home_action.setToolTip("Go back to Homescreen")
        toolbar.addAction("Edit")
        self.tag_action = toolbar.addAction("Tag")
        self.tag_action.setShortcut("Ctrl + T")
        self.tag_action.triggered.connect(self.tag_comics)
        self.toggle_action = toolbar.addAction("Toggle Sidebar")
        self.toggle_action.triggered.connect(self.toggle_sidebar)
        self.toggle_action.setShortcut("Ctrl+B")
        self.toggle_action.setToolTip("Toggle file tree sidebar")
        self.refresh_action = toolbar.addAction("Update")
        self.refresh_action.triggered.connect(scan_and_clean)
        self.refresh_action.setShortcut("Ctrl + U")

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search comics..")
        self.search_bar.setFixedWidth(200)
        self.search_bar.editingFinished.connect(
            lambda: self.search(self.search_bar.text())
        )
        toolbar.addWidget(self.search_bar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.progress_bar.hide()

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
        self.file_tree.clicked.connect(self.on_folder_select)
        self.file_tree.setHeaderHidden(True)

        for i in range(1, self.file_model.columnCount()):
            self.file_tree.hideColumn(i)

        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)
        left_layout.addWidget(self.file_tree, stretch=1)
        left_layout.addWidget(QLabel("This is temporary."), stretch=1)
        self.splitter = QSplitter()
        self.splitter.addWidget(left_widget)

        self.content_area = QWidget()
        content_layout = QVBoxLayout(self.content_area)
        with RepoWorker("D://adams-comics//.covers") as repo_worker:
            continue_list, review_list = repo_worker.run()

        # stats_bar = self.create_stats_bar()
        # stats_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # stats_bar.setMaximumHeight(60)
        # left_layout.addWidget(stats_bar, stretch=2)
        continue_reading = self.create_continue_reading_area(continue_list)
        # need_review = self.create_review_area(review_list)
        rss = self.create_rss_area(20)

        # content_layout.addWidget(stats_bar, stretch=1)
        content_layout.addWidget(continue_reading, stretch=3)
        # content_layout.addWidget(need_review, stretch=3)
        content_layout.addWidget(rss, stretch=3)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.content_area)
        self.splitter.addWidget(self.stack)
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.addWidget(self.splitter)
        lay.setContentsMargins(0, 0, 0, 0)
        self.splitter.setSizes([100, 650])

        self.browse_splitter = QSplitter()
        self.stack.addWidget(self.browse_splitter)

        self.search_layout = QVBoxLayout()
        self.search_display = QWidget()
        self.search_display.setLayout(self.search_layout)
        self.stack.addWidget(self.search_display)

        self.setCentralWidget(container)

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
        list_of_info: list[GUIComicInfo | RSSComicInfo],
        header: str,
        upon_clicked: Callable,
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
        img_height = 200

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

        def make_click_handler(func, comic):
            def handler():
                if inspect.iscoroutinefunction(func):
                    asyncio.create_task(func(comic))
                else:
                    func(comic)

            return handler

        for comic in list_of_info:

            if isinstance(comic, RSSComicInfo):
                pixmap = self.load_pixmap_from_url(comic.cover_url)
            else:
                pixmap = QPixmap(comic.cover_path)

            title_name = comic.title
            comic_button = ClickableComicWidget(title_name, pixmap, img_height)
            comic_button.clicked.connect(make_click_handler(upon_clicked, comic))

            layout.addWidget(comic_button)

        scroll_area.setWidget(container)
        wrapper_widget = QWidget()
        wrapper_layout = QVBoxLayout(wrapper_widget)
        wrapper_layout.addWidget(title)
        wrapper_layout.addWidget(scroll_area)

        return wrapper_widget

    def open_reader(self, comic: GUIComicInfo) -> None:
        """
        Open a comic reader for the specified comic.

        Args:
            Dictionary containing information about the comic
            including filepath and database id.
        """
        cont = ReadingController(comic)
        cont.read_comic()

    def print_hi(self, comic_info: GUIComicInfo) -> None:
        print("Hi " + comic_info.title + "!")

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

    def create_review_area(
        self, list_of_unreviewed_comics: list[GUIComicInfo]
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
            upon_clicked=self.open_review_panel,
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
        self.rss_controller = DownloadControllerAsync(
            view=self, service=DownloadServiceAsync()
        )
        return self.create_scroll_area(
            recent_comics_list,
            header="GetComics RSS Feed",
            upon_clicked=self.rss_controller.handle_rss_comic_clicked,
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
        layout.setContentsMargins(0, 0, 0, 0)

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

    def on_folder_select(self, index):
        folder_path = self.file_model.fileName(index)
        pub_id = folder_path[0]

        if pub_id.isdigit():
            pub_id = int(pub_id)
            if pub_id != 0:
                with RepoWorker("D://adams-comics//.covers") as folder_info_getter:
                    grid_view_data = folder_info_getter.get_folder_info(pub_id)

                    if hasattr(self, "grid_view") and self.grid_view is not None:
                        space = self.browse_splitter.indexOf(self.grid_view)
                        if space != -1:
                            widget = self.browse_splitter.widget(space)
                            widget.setParent(None)
                            widget.deleteLater()

                    self.grid_view = ComicGridView(grid_view_data)
                    self.grid_view.metadata_requested.connect(self.show_metadata_panel)

                    if self.browse_splitter.count() == 0:
                        self.browse_splitter.addWidget(self.grid_view)
                    else:
                        self.browse_splitter.insertWidget(0, self.grid_view)
                    self.stack.setCurrentWidget(self.browse_splitter)

    def show_metadata_panel(self, comic_info: GUIComicInfo):
        with RepoWorker("D://adams-comics//.covers") as info_getter:
            comic_metadata = info_getter.get_complete_metadata(comic_info.primary_id)

        if hasattr(self, "metadata_panel") and self.metadata_panel is not None:
            index = self.browse_splitter.indexOf(self.metadata_panel)
            if index != -1:
                old = self.browse_splitter.widget(index)
                old.setParent(None)
                old.deleteLater()

        self.metadata_panel = MetadataPanel(comic_metadata)

        if self.browse_splitter.count() == 1:
            self.browse_splitter.addWidget(self.metadata_panel)
        elif self.browse_splitter.count() == 2:
            self.browse_splitter.insertWidget(1, self.metadata_panel)

        total = sum(self.browse_splitter.sizes())
        self.browse_splitter.setSizes([int(total * 0.8), int(total * 0.2)])

        file_tree_sizes = self.splitter.sizes()
        if len(file_tree_sizes) == 2:
            total = file_tree_sizes[0] + file_tree_sizes[1]
            self.splitter.setSizes([0, total])

    def toggle_sidebar(self):
        sizes = self.splitter.sizes()
        if sizes[0] > 0:
            self.sidebar_width = sizes[0]
            self.splitter.setSizes([0, sizes[1] + sizes[0]])
        else:
            previous = getattr(self, "sidebar_width", 150)
            self.splitter.setSizes([previous, sizes[1]])

    def go_home(self):
        self.stack.setCurrentWidget(self.content_area)

    def search(self, text):
        display_info = text_search(text)
        search_view = ComicGridView(display_info)
        for i in reversed(range(self.search_layout.count())):
            widget_to_remove = self.search_layout.itemAt(i).widget()
            if widget_to_remove:
                widget_to_remove.setParent(None)

        self.search_layout.addWidget(search_view)
        self.stack.setCurrentWidget(self.search_display)

    def open_review_panel(self, comic_info: GUIComicInfo):
        self.metadata_popup = MetadataDialog(comic_info)
        self.metadata_popup.show()

    def tag_comics(self):
        run_tagger(self)

    def get_user_match(self, query_results: list[dict], actual_comic, filepath: str):

        dialog = ComicMatcherUI(actual_comic, query_results, Path(filepath))
        if dialog.exec() == QDialog.Accepted:
            selected = dialog.get_selected_result()
            if selected:
                return selected

        print("User cancelled or no selection made.")
        return None

    def update_status(self, message: str) -> None:
        """
        Update the status bar with a message.

        Args:
            message: The message to display in the
        status bar.
        """
        self.statusBar().showMessage(message, 4000)

    def update_progress_bar(self, value: int):
        self.progress_bar.show()
        self.progress_bar.setValue(value)
        if value >= 100:
            QTimer.singleShot(1500, self.progress_bar.hide)
            self.progress_bar.setValue(0)


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


async def main():
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    window = HomePage()
    window.show()
    with loop:
        await loop.run_forever()


if __name__ == "__main__":
    scan_and_clean()
    asyncio.run(main())

"""
Code for creating the home-page of the app.
"""

import asyncio
import inspect
from pathlib import Path
from typing import Callable, Optional, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from classes.helper_classes import GUIComicInfo, MainViewType, RSSComicInfo
from database.gui_repo_worker import RepoWorker
from download_controller import DownloadControllerAsync
from general_comic_widget import GeneralComicWidget
from rss.rss_controller import RSSController
from rss.rss_repository import RSSRepository


class HomeView(QWidget):
    """
    A class for creating and managing the home-page/landing-page of the app.
    """

    VIEW_TYPE = MainViewType.HOME_VIEW
    openReader = Signal(GUIComicInfo)
    asyncError = Signal(object)
    statusMessage = Signal(str)
    downloadProgress = Signal(int)

    def __init__(self, db_path: Path):
        """
        Creats the different views off the home-page.

        NOTE: Review-area and and recommended-area are still WIP.

        Args:
            db_path (Path): The path of the database.
        """
        super().__init__()
        self.DB_PATH = db_path
        content_layout = QVBoxLayout(self)

        # stats_bar = self.create_stats_bar()
        # stats_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # stats_bar.setMaximumHeight(60)
        with RepoWorker() as repo_worker:
            continue_list, progress_list, review_list = repo_worker.run()
        self.continue_reading = self.create_continue_reading_area(
            continue_list, progress_list
        )
        # need_review = self.create_review_area(review_list)
        self.rss = self.create_rss_area(10)

        # content_layout.addWidget(stats_bar, stretch=1)
        content_layout.addWidget(self.continue_reading, stretch=3)
        # content_layout.addWidget(need_review, stretch=3)
        content_layout.addWidget(self.rss, stretch=3)

    def create_scroll_area(
        self,
        list_of_info: Sequence[GUIComicInfo | RSSComicInfo],
        header: str,
        left_clicked: Optional[Callable],
        right_clicked: Optional[Callable],
        double_left_clicked: Optional[Callable],
        progresses: Optional[list[float]] = None,
    ) -> QWidget:
        """
        Create a horizontal scroll area populated with comic widgets.

        Args:
            list_of_dicts: List of dictionaries containing comic
        information.
            header: Text for the scroll area section title.
            upon_clicked: Callback function to execute when a
        comic is clicked.

        Returns:
            A configured QScrollArea with clickable comic widgets.
        """

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        container = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(16)
        container.setLayout(layout)

        title = QLabel(header)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            """font-size: 18px;
                             font-weight: bold; padding: 10px;"""
        )

        def wrap_handler(func) -> Optional[Callable]:
            """Wraps async function calls so that they flag errors."""
            if func is None:
                return None
            if inspect.iscoroutinefunction(func):

                def wrapper(*args, **kwargs):
                    """Wrap the callback"""
                    task = asyncio.create_task(func(*args, **kwargs))
                    task.add_done_callback(self.async_error_propagate)

                return wrapper
            return func

        for pos, comic in enumerate(list_of_info):
            progress = progresses[pos] if progresses else None
            comic_widget = GeneralComicWidget(
                comic,
                wrap_handler(left_clicked),
                right_clicked,
                double_left_clicked,
                progress=progress,
            )

            layout.addWidget(comic_widget)

        scroll_area.setWidget(container)
        wrapper_widget = QWidget()
        wrapper_layout = QVBoxLayout(wrapper_widget)
        wrapper_layout.addWidget(title)
        wrapper_layout.addWidget(scroll_area)

        return wrapper_widget

    def async_error_propagate(self, error) -> None:
        """Emits the `asyncError` signal so the main layer can capture"""
        self.asyncError.emit(error)

    def open_reader(self, comic: GUIComicInfo) -> None:
        """Emits the signal to start reading a comic."""
        self.openReader.emit(comic)

    def create_continue_reading_area(
        self, read_comics: list[GUIComicInfo], progress: list[float]
    ) -> QWidget:
        """
        Creates a scroll area for comics marked as continue reading.

        Args:
            list_of_comics_marked_as_read: List of comics to display.
        """
        return self.create_scroll_area(
            read_comics,
            header="Continue Reading",
            left_clicked=self.open_reader,
            right_clicked=None,
            double_left_clicked=None,
            progresses=progress,
        )

    def create_recommended_reading_area(
        self, recommended_comics: list[GUIComicInfo]
    ) -> QWidget:
        """
        Creates a scroll area for comics marked as recommended.

        Args:
            list_of_recommended_comics: List of recommended
        comics to display.
        """
        return self.create_scroll_area(
            recommended_comics,
            header="Recommended Next Read",
            left_clicked=self.open_reader,
            right_clicked=None,
            double_left_clicked=None,
        )

    # def create_review_area(
    #     self, list_of_unreviewed_comics: list[GUIComicInfo]
    # ) -> QWidget:
    #     """
    #     Creates a scroll area for comics marked as requiring
    #     review.

    #     Args:
    #         list_of_unreviewed_comics: List of unreviewed comics
    #     to display.
    #     """
    #     return self.create_scroll_area(
    #         list_of_unreviewed_comics,
    #         header="Write a review...",
    #         left_clicked=self.open_review_panel,
    #         right_clicked=None,
    #         double_left_clicked=None,
    #     )

    def create_rss_area(self, num: int = 12) -> QWidget:
        """
        Creates a scroll area for RSS feed comics.

        Fetches recent comics from the RSS controller and
        creates a scroll area with download functionality
        for each comic.
        """
        repository = RSSRepository(self.DB_PATH)
        rss_cont = RSSController(repository)
        recent_comics_list = rss_cont.run(num)
        self.download_controller = DownloadControllerAsync(view=self)
        return self.create_scroll_area(
            recent_comics_list,
            header="GetComics RSS Feed",
            left_clicked=self.download_controller.handle_rss_comic_clicked,
            right_clicked=None,
            double_left_clicked=None,
        )

    def update_status(self, message: str) -> None:
        """Emits a status message for the status bar in the main window to display."""
        self.statusMessage.emit(message)

    def update_download_progress(self, percent: int) -> None:
        """Emits the download progress."""
        self.downloadProgress.emit(percent)

    # def create_stats_bar(self, files_num: int, storage_val: float) -> QWidget:
    #     """
    #     Create and return a statistics bar widget.

    #     Returns:
    #         A QWidget containing comic library statistics.
    #     """

    #     def create_stat_widget(title: str, image_path: str, value: str) -> QWidget:
    #         """
    #         Create a single statistic widget.

    #         Args:
    #             title: The statistic title.
    #             image_path: Path to the icon image.
    #             value: The statistic value to display.

    #         Returns:
    #             A QWidget displaying the statistic with title, icon
    #         and value.
    #         """
    #         widget = QWidget()
    #         layout = QVBoxLayout()
    #         layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    #         widget.setLayout(layout)

    #         title_label = QLabel(title)
    #         title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    #         pixmap = QPixmap(image_path)
    #         image_label = QLabel()
    #         image_label.setPixmap(
    #             pixmap.scaled(
    #                 30,
    #                 30,
    #                 Qt.AspectRatioMode.KeepAspectRatio,
    #                 Qt.TransformationMode.SmoothTransformation,
    #             )
    #         )
    #         image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    #         value_label = QLabel(value)
    #         value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    #         layout.addWidget(title_label)
    #         layout.addWidget(image_label)
    #         layout.addWidget(value_label)

    #         return widget

    #     stats = QWidget()
    #     layout = QHBoxLayout(stats)
    #     layout.setContentsMargins(0, 0, 0, 0)

    #     layout.addWidget(
    #         create_stat_widget(
    #             "Number of Comics",
    #             "D:\\comic_library\\comic_gui\\comicbook.png",
    #             str(files_num),
    #         )
    #     )

    #     layout.addWidget(
    #         create_stat_widget(
    #             "Storage",
    #             "D:\\comic_library\\comic_gui\\storage.png",
    #             f"{round(storage_val, 2)} GB",
    #         )
    #     )

    #     final_widget = QWidget()
    #     final_layout = QVBoxLayout()
    #     final_widget.setLayout(final_layout)
    #     title = QLabel("Your Statistics")
    #     title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    #     title.setStyleSheet(
    #         """font-size: 12px;
    #                          font-weight: bold; padding: 2px;"""
    #     )
    #     final_layout.addWidget(title)
    #     final_layout.addWidget(stats)

    #     return final_widget

"""
A collection of classes for reading comics, preloading images, managing the order
of the comic images, so reading is snappy, responsive and the code structure is
expandable and future-proof.
"""

import logging
import os
import zipfile
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum, auto
from io import BytesIO
from pathlib import Path
from typing import overload

from dotenv import load_dotenv
from PIL import Image
from PySide6.QtCore import (
    QBuffer,
    QByteArray,
    QIODevice,
    QObject,
    QRunnable,
    Qt,
    QThreadPool,
    Signal,
)
from PySide6.QtGui import (
    QIcon,
    QImage,
    QImageReader,
    QKeySequence,
    QPainter,
    QPixmap,
    QShortcut,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QToolBar,
    QVBoxLayout,
)

from my_project.classes.helper_classes import GUIComicInfo
from my_project.ui.widgets.metadata_gui_panel import MetadataDialog

load_dotenv()
resources_path = os.getenv("FRONTEND_RESOURCES")
if not resources_path:
    raise RuntimeError("FRONTEND_RESOURCES environment variable is not set.")
IMAGES = Path(resources_path)
logging.basicConfig(
    filename="debug.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


class ComicError(Exception):
    """Base exception for Comic-related issues."""


class PageIndexError(ComicError):
    """Raised when a page index is out of range."""


class ImageLoadError(ComicError):
    """Raised when an image fails to load."""


class ReadMode(Enum):
    """
    Enum for the current mode of reading. This affects the layout of the pages,
    and the behaviour of the forward and backward buttons.
    """

    SINGLE_PAGE = auto()
    DOUBLE_PAGE = auto()
    MANGA = auto()
    INFINITY = auto()


class PageType(Enum):
    """
    An Enum containing the diferent kinds of pages that would exist within a
    comic archive. These are used for the logic within the comic page sequence.
    """

    UNKNOWN = auto()
    COVER = auto()
    BACK_COVER = auto()
    NORMAL = auto()
    SPREAD = auto()


@dataclass(slots=True)
class PageInfo:
    """
    A data class for storing key information on comic pages within an archive.
    """

    filename: str
    index: int
    page_type: PageType = PageType.UNKNOWN


@dataclass(slots=True)
class DisplayPage:
    """
    A data class for storing the pages indices within a 'page'
    displayed to the user.
    """

    pages: tuple[int, ...]


class Comic:
    """A class which represents a particular comic."""

    def __init__(
        self, comic_info: GUIComicInfo, start_index: int = 0, max_cache: int = 10
    ) -> None:
        """
        Creates an instance of the Comic Class and sets up a lot of instance variables that will be used
        in the following function calls.

        Args:
            comic_info (GUIComicInfo): A pydantic model including all the relevant data the UI needs to
                display the comic.
            start_index (int, optional): The page index to start the reader from, usually the last read page.
                Defaults to 0.
            max_cache (int, optional): The number of pages to keep in memory at all time. Defaults to 10.

        Raises:
            ComicError: This error is raised when no images are found in the comic archive folder.
        """
        self.path = comic_info.filepath
        self.filename = comic_info.filepath.stem
        self.zip = zipfile.ZipFile(comic_info.filepath, "r")
        self.image_names = sorted(
            name
            for name in self.zip.namelist()
            if name.lower().endswith((".jpg", ".jpeg", ".png"))
        )
        if not self.image_names:
            raise ComicError("No images found in the file.")
        self.pages = [PageInfo(n, pos) for pos, n in enumerate(self.image_names)]
        self.pages[0].page_type = PageType.COVER
        self.pages[-1].page_type = PageType.BACK_COVER
        for i in self.pages:
            self.analyse_page(i)
        self.total_pages = len(self.image_names)
        self.size = comic_info.filepath.stat().st_size
        self.cache: OrderedDict[str, bytes] = OrderedDict()
        self.max_cache = max_cache
        self.current_index: int = start_index
        self.id = comic_info.primary_id
        self.info = comic_info

    def set_page_index(self, index: int) -> None:
        """Sets the current page of the comic to 'index'."""
        self.current_index = index

    def get_image_data(self, index: int) -> bytes:
        """
        Gets the comic image data corresponding to the index. First it searches through the cache
        and then goes to the zipfile if it is not in recent memory.

        Args:
            index (int): The page index of the required page.

        Raises:
            PageIndexError: An error returned if the index is not valid for the comic.
            ImageLoadError: An error returned if the code couldnt read the image from
                the comic archive.

        Returns:
            bytes: The raw bytes of the image at page: index.
        """
        if index < 0 or index >= self.total_pages:
            raise PageIndexError(f"Index {index} out of range.")

        name = self.image_names[index]
        if name in self.cache:
            self.cache.move_to_end(name)
            return self.cache[name]

        try:
            with self.zip.open(name) as file:
                data = file.read()
        except Exception as e:
            raise ImageLoadError(f"Failed to read image {name}: {e}") from e

        self.cache[name] = data
        if len(self.cache) > self.max_cache:
            self.cache.popitem(last=False)

        return data

    def next_image_data(self) -> bytes:
        """
        Increases the index counter by one and gets the bytes content of the next page.

        Returns:
            bytes: The raw bytes of the image to display.
        """
        self.current_index += 1
        return self.get_image_data(self.current_index)

    def image_size(self, index: int) -> tuple[int, int]:
        """
        Gets the size of an image within the comic archive.

        Reads the image data via QBuffer in read-only mode and then analyses
        the header to get the size.

        Args:
            index (int): The index of the comic image to anaylse, the indices
            are taken from the order of pages in the comic archive.

        Raises:
            ImageLoadError: Raised if the image bytes cannot be read.

        Returns:
            tuple[int, int]: The image size in (width, height) format.
        """
        page = self.pages[index]
        try:
            image_bytes = self.zip.read(page.filename)
        except Exception as e:
            raise ImageLoadError(f"Failed to read image {page.filename}: {e}") from e
        buffer = QBuffer()
        buffer.setData(QByteArray(image_bytes))
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)

        reader = QImageReader(buffer)
        size = reader.size()
        return size.width(), size.height()

    def analyse_page(self, page: PageInfo) -> PageInfo:
        """
        Decides the kind of page that the image is by looking at the size.

        Then edits the `page_type` attribute of the `PageInfo` in place depending
        on the aspect ratio of the image.

        Args:
            page (PageInfo): The PageInfo object belong to the comic image to look at.

        Returns:
            PageInfo: The edited PageInfo object with its `page_type` updated.
        """
        if page.page_type != PageType.UNKNOWN:
            return page

        try:
            width, height = self.image_size(page.index)
            page.page_type = (
                PageType.SPREAD if width / height > 1.3 else PageType.NORMAL
            )
        except ImageLoadError:
            page.page_type = PageType.NORMAL
        return page


class ReadingSequence(QObject):
    """
    A class to manage the order of comic display images.

    The order depends on the reading type.
    """

    front_cover_reached = Signal()
    back_cover_reached = Signal()

    def __init__(self, comic: Comic):
        """
        Creates the sequence in single page mode as default.

        Creates the list `self.display_pages` the contains the order of the comic
        images to display.
        Creates the dictionary `self.page_to_position` to track the relationship between
        index number and page number.

        Args:
            comic (Comic): The data of the Comic to be read.
        """
        super().__init__()
        self.comic = comic
        self.mode = ReadMode.SINGLE_PAGE

        self.display_pages: list[DisplayPage] = []
        self.page_to_position: dict[int, int] = {}

        self.build_sequence()
        self.position = self.archive_index_to_position(comic.current_index)

    def set_mode(self, mode: ReadMode) -> None:
        """
        Rebuilds the reading sequence depending on the inputted reading mode.

        The index number is recorded and then the new page number in the new sequence
        is updated to match the last seen comic image.

        Args:
            mode (ReadMode): The reading mode that dictates the layout of the pages
        """
        current_archive_page = self.current_display()[0]

        self.mode = mode
        self.build_sequence()

        self.position = self.archive_index_to_position(current_archive_page)

    def build_sequence(self) -> None:
        """
        A helper function which decides the correct way to rebuild the sequence
        by looking at the `self.mode` attribute.

        Once the sequence is rebuilt, the `self.page_to_position` dictionary is also
        rebuilt to match the new sequence.
        """
        self.page_to_position.clear()
        match self.mode:
            case ReadMode.SINGLE_PAGE:
                self.display_pages = self.build_single()

            case ReadMode.DOUBLE_PAGE:
                self.display_pages = self.build_double()

            case ReadMode.MANGA:
                self.display_pages = self.build_manga()

            case ReadMode.INFINITY:
                raise NotImplementedError("Infinity reading mode is not implemented.")

        for pos, display in enumerate(self.display_pages):
            for page in display.pages:
                self.page_to_position[page] = pos

    def build_double(self) -> list[DisplayPage]:
        """
        Loops through the PageInfo's in self.comic and uses its `page_type`
        to decide whether the image should be shown in double-page or single-page.

        Returns:
            list[DisplayPage]: The new display sequence containing an ordered list
            of DisplayPage's.
        """
        pages = []
        i = 0
        while i < self.comic.total_pages:
            display = self.build_display_page(i)
            pages.append(display)

            if len(display.pages) == 2:
                i += 2
            else:
                i += 1

        return pages

    def build_single(self) -> list[DisplayPage]:
        """
        Creates the sequence for single-page reading mode.

        This just creates a DisplayPage instance for each image in the comic
        archive.

        Returns:
            list[DisplayPage]: Ordered list of display pages.
        """
        return [DisplayPage((page.index,)) for page in self.comic.pages]

    def build_manga(self) -> list[DisplayPage]:
        """
        Creates the sequence for manga reading mode.

        It builds the single-page mode and then reverses it so that the archive is
        read right-to-left.

        Returns:
            list[DisplayPage]: Ordered list of display pages.
        """
        return list(reversed(self.build_single()))

    def build_display_page(self, index: int) -> DisplayPage:
        """
        Creates a DisplayPage for a given image in the comic archive.

        Uses the `page_type` attribute or the position within the archive to decide
        how to display to the user.

        This is only used when building the double-page sequence.

        Args:
            index (int): The position of the comic image within the comic archive.

        Raises:
            ValueError: If the PageInfo has its `page_type` as UNKNOWN.

        Returns:
            DisplayPage: The DisplayPage that has the correct comic image indices.
        """
        page = self.comic.pages[index]

        if page.page_type in (PageType.COVER, PageType.BACK_COVER):
            return DisplayPage((index,))

        if page.page_type == PageType.UNKNOWN:
            raise ValueError(f"Page at position {index} has not been analysed yet.")

        if page.page_type == PageType.SPREAD:
            return DisplayPage((index,))

        if index == self.comic.total_pages - 1:
            return DisplayPage((index,))

        next_page = self.comic.pages[index + 1]

        if next_page.page_type in (PageType.BACK_COVER, PageType.SPREAD):
            return DisplayPage((index,))

        return DisplayPage((index, index + 1))

    def archive_index_to_position(self, index: int) -> int:
        """
        Gets the position in the ordered list of DisplayPages from
        the image index in the comic archive.

        Args:
            index (int): The index of the image in the archive.

        Returns:
            int: The position in the Display order.
        """
        return self.page_to_position[index]

    def update_position(self, index: int):
        """
        Updates the current position of the sequence.

        Args:
            index (int): The index of the image in the archive.
        """
        self.position = self.archive_index_to_position(index)

    def position_to_archive_index(self) -> int:
        """
        Gets the index of the image in the archive from the position in
        the DisplayPage sequence.

        Returns:
            int: Index of the comic image in the archive.
        """
        display = self.display_pages[self.position]
        return display.pages[0]

    def next(self):
        """
        Increases the position counter by one if there are more pages
        to be read. Otherwise, emits the back cover signal.
        """
        if self.position < len(self.display_pages) - 1:
            self.position += 1
        else:
            self.back_cover_reached.emit()

    def prev(self):
        """
        Decreases the position counter by one if there are pages behind
        the current one. Otherwise emits the front cover signal.
        """
        if self.position > 0:
            self.position -= 1
        else:
            self.front_cover_reached.emit()

    def current_display(self) -> tuple[int, ...]:
        """
        Gets the current DisplayPage to send to the reader.

        Returns:
            tuple[int, ...]: A tuple of the comic image indices to include
            in the view. Should have a maximum length of two.
        """
        return self.display_pages[self.position].pages


class ImageLoadSignals(QObject):
    """
    Qt signal container for asynchronous image loading tasks.

    This object defines the signals emitted by :class`ImageLoadTask`
    instances during background execution. It provides a communication
    bridge between worker threads and main GUI thread.

    Signals:
        finished(int, QPixmap):
            Emitted when an image has been successfully loaded and converted
            into a :class`QPixmap`.

            Args:
                int:
                    The page index associated with the loaded image.
                QPixmap:
                    The resulting pixmap ready for display.

        error (int, str):
            Emitted when an exception occurs while loading or processing
            an image.

            Args:
                int:
                    The page index that failed to load.
                str:
                    Human-readable error message describing the failure.

    Signals are emitted from worker thread but are automatically delivered
    safely through Qt's queued connection system when connected to slots in
    the GUI thread.
    """

    finished = Signal(int, QPixmap)
    error = Signal(int, str)


class ImageLoadTask(QRunnable):
    """
    Background worker task responsible for loading and converting a comic page.

    This QRunnable is executed by a :class`QThreadPool` to avoid blocking the
    GUI thread while image data is fetched and decoded. The task retrieves raw
    image bytes from a :class`Comic` instance, converts them into a Pillow image,
    then transforms the result into a Qt-compatible :class`QPixmap`.

    Attributes:
        comic (Comic):
            Comic data source used to retrieve page image data.

        index (int):
            Zero-based page index to load.

        signals (ImageLoadSignals):
            Signal container used to notify listeners when loading succeeds or fails.

    Workflow:
        1. Fetch raw image bytes from comic source.
        2. Decode image data using Pillow.
        3. Convert the image to RGBA format.
        4. Create a :class`QImage` from the raw pixel buffer.
        5. Convert the QImage into a :class`QPixmap`.
        6. Emit either a success or error signal.

    Notes:
        - The image is fully loaded into memory via ``image.load()`` before
        conversion to ensure thread-safe access.
        - RGBA conversion guarantees a predictable pixel format for Qt.
        - Exceptions are caught internally and reported through the ``error``
        signal instead of propagating across threads.
    """

    def __init__(self, comic: Comic, index: int):
        """Initialises the class by assigning the attributes."""
        super().__init__()
        self.comic = comic
        self.index = index
        self.signals = ImageLoadSignals()

    def run(self):
        """
        Execute the image loading task.

        This method is invoked automatically by Qt's thread pool when
        the runnable is scheduled. It performs image retrieval, decoding,
        conversion, and signal emission.

        Emits:
            signals.finished:
                When the image is successfuly loaded and converted.

            signals.error:
                When any exception occurs during processing.

        Raises:
            No exceptions are propageted directly. All exceptions are caught
            and forwarded through the ``error`` signal.
        """
        try:
            data = self.comic.get_image_data(self.index)
            image = Image.open(BytesIO(data))
            image.load()
            image = image.convert("RGBA")

            qimage = QImage(
                image.tobytes("raw", "RGBA"),
                image.width,
                image.height,
                QImage.Format.Format_RGBA8888,
            )
            pixmap = QPixmap.fromImage(qimage)

            self.signals.finished.emit(self.index, pixmap)

        except Exception as e:
            self.signals.error.emit(self.index, str(e))


class PagePreloader(QObject):
    """
    Asynchronous image preloading and caching manager for comic pages.

    The PagePreloader maintains an in-memory cache of nearby comic page
    images and loads them asynchronously using :class`QThreadPool`.
    Its primary goal is to improve navigation responsiveness by ensuring
    pages close to the current reading position are already decoded and
    available for immediate display.

    Signals:
        page_ready (int):
            Emitted when a page has been successfully loaded and cached.

            Args:
                int:
                    The index of the page that is now available.

    Attributes:
        comic (Comic):
            Comic source used to retrieve page image data.

        forward_buff (int):
            Number of pages after the current page that should be
            preloaded. This is larger since the chance is that people
            would need to read forward than go back.

        backward_buff (int):
            Number of pages before the current page that should be
            preloaded.

        image_cache (dict[int, QPixmap]):
            In-memory cache mapping page indices to loaded pixmaps.

        loading (set[int]):
            Set of page indices currently being loaded. Used to prevent
            duplicate scheduling.

        pool (QThreadPool):
            Thread pool used to execute background loading tasks.

    Caching strategy:
        The preloader maintains a sliding window centered around the
        current page.Pages outside the buffer range are removed from
        memory to reduce resource usage.

    Threading:
        Image loading occurs on worker threads managed by the internal
        thread pool, while cache updates and signal emissions occur
        safely through Qt's signal-slot system. There is a priority system
        in place to ensure that the direct next pages are loaded first before
        others for a smoother reading experience.
    """

    page_ready = Signal(int)
    page_failed = Signal(int, str)

    def __init__(self, comic: Comic):
        """
        Intialise the page preloader.

        Args:
            comic (Comic): Comic source for page image retrieval.
        """
        super().__init__()
        self.comic = comic

        self.forward_buff = 16
        self.backward_buff = 4

        self.image_cache: dict[int, QPixmap] = {}
        self.pending: list[int] = []
        self.loading: set[int] = set()
        self.wanted: set[int] = set()
        self.failed: set[int] = set()

        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(6)

    def get_load_order(self, indices: tuple[int, ...]) -> list[int]:
        """
        Orders the list of pages to be loaded into the correct order,
        with the highest priority loads first.

        Args:
            indices (tuple[int, ...]): The indices of the current display pages.

        Returns:
            list[int]: The ordered list of indices for the next pages to be read.
            They are ordered with descending priority.
        """
        pages = list(indices)

        for offset in range(1, self.forward_buff + 1):
            page = indices[-1] + offset
            if page < self.comic.total_pages:
                pages.append(page)

        for offset in range(1, self.backward_buff + 1):
            page = indices[0] - offset
            if page >= 0:
                pages.append(page)

        return pages

    def preload(self, indices: tuple[int, ...]) -> None:
        """
        Preload pages surrounding the current reading position.

        Pages outside the desired range are evicted, and missing pages
        inside the range are added to the pending list.

        Args:
            indices (tuple[int, ...]): Current display page indices around which
            preloading should occur.

        Notes:
            - Already cached pages are reused.
            - Pages currently loading are not scheduled again.
            - Cache eviction occurs immediately for pages outside
            the preload window.
        """
        load_order = self.get_load_order(indices)
        wanted = set(load_order)
        self.wanted = wanted

        for idx in list(self.image_cache):
            if idx not in wanted:
                del self.image_cache[idx]

        self.pending = [
            page
            for page in load_order
            if page not in self.loading and page not in self.image_cache
        ]

        self.fill_workers()

    def fill_workers(self):
        """
        Ensures that all workers in the Pool have a task, provided there are tasks
        to complete.
        """
        while len(self.loading) < self.pool.maxThreadCount() and self.pending:
            page = self.pending.pop(0)
            self.schedule_load(page)

    def schedule_load(self, index: int):
        """
        Schedule asynchronous loading of a page image.

        Creates a :class`ImageLoadTask`, connects its signals
        and submits it to the internal thread pool for execution.

        Args:
            index (int): Page index to load.

        Notes:
            The page index is added to ``loading`` immediately to prevent
            duplicate scheduling before the worker thread begins execution.
        """
        self.loading.add(index)

        task = ImageLoadTask(self.comic, index)
        task.signals.finished.connect(self.on_loaded)
        task.signals.error.connect(self.on_error)

        self.pool.start(task)

    def on_loaded(self, index: int, pixmap: QPixmap):
        """
        Handle successful completion of an image loading task.

        The index of the loaded pixmap is checked to ensure it is
        still wanted, then it's inserted into the cache and the page
        is marked as no longer loading.

        Args:
            index (int): Index of the loaded page.
            pixmap (QPixmap): Loaded page image.

        Emits:
            page_ready: Emitted after the image has been stored
            in the cache.
        """
        self.loading.discard(index)

        if index in self.wanted:
            self.image_cache[index] = pixmap
            self.page_ready.emit(index)
        self.fill_workers()

    def on_error(self, index: int, message: str):
        """
        Handle failure during asynchronous page loading.

        Removes the page from the active loading set and logs
        the error.

        Args:
            index (int): Index of the page that failed to load.
            message (str): Description of the error that occured.

        Notes:
        Failed pages are not automatically retried.
        """
        self.loading.discard(index)
        logging.error(
            "Failed to load page %d (%s): %s",
            index,
            self.comic.pages[index].filename,
            message,
        )
        self.failed.add(index)
        self.page_failed.emit(index, message)
        self.fill_workers()

        # TODO: Add retry method for pages that fail to load.
        # Need to implement some kind of diagnostic


class Navigation(QDialog):
    """
    A popup window for asking the user which page to navigate to.
    """

    def __init__(self, max_pages: int):
        """
        Creates the instance variables like the line edit.

        Args:
            max_pages (int): The number of pages in the comic.
        """
        super().__init__()

        layout = QVBoxLayout(self)
        instruct = QLabel(f"Enter page to navigate to. ({max_pages} pages)")
        self.max_pages = max_pages
        self.line_edit = QLineEdit()
        self.line_edit.returnPressed.connect(self.ok_pressed)
        self.error_message = QLabel("")
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self.ok_pressed)
        buttons.rejected.connect(self.reject)
        layout.addWidget(instruct)
        layout.addWidget(self.line_edit)
        layout.addWidget(self.error_message)
        layout.addWidget(buttons)

    def ok_pressed(self) -> None:
        """
        Checks that the entered value is first a number, and second within
        the correct range.

        If not, a suggestive error message is displayed to the user.
        """
        try:
            page_num = int(self.text)
        except ValueError:
            self.error_message.setText("Please enter a number.")
            return

        if 0 <= page_num <= self.max_pages:
            self.accept()
        else:
            self.error_message.setText(
                f"Please enter a number between 1 and {self.max_pages - 1}."
            )
            return

    @property
    def text(self) -> str:
        """
        Returns the text in the line edit.
        """
        return self.line_edit.text()


class SimpleReader(QMainWindow):
    """
    The main reading window.

    Combines image pre-loading with a couple of user-friendly menu
    features such as the ability to add comments or see expanded metadata
    for the comic.

    Signals:
        closed (str, int):
    """

    closed = Signal(str, int)

    def __init__(self, comic: Comic):
        """
        Creates the base window by opening the comic on the currenly read index
        and loading a certain amount of images before and after.

        Creates a toolbar for comic navigation and commenting.

        Args:
            comic (Comic): An instance of the :class`Comic` that gives useful data
                like unique identifier and current saved page from the database.
        """
        super().__init__()

        self.comic = comic

        self.sequence = ReadingSequence(comic)
        self.preloader = PagePreloader(comic)
        self.preloader.page_ready.connect(self.on_page_ready)

        self.setWindowTitle("Comic Reader")

        self.image_label = QLabel("Loading...", alignment=Qt.AlignmentFlag.AlignCenter)
        self.page_label = QLabel(
            f"Page {comic.current_index}", alignment=Qt.AlignmentFlag.AlignCenter
        )

        self.toolbar = QToolBar("Navigation Tools")
        self.prev_action = self.toolbar.addAction(
            QIcon(str(IMAGES / "arrow_left.svg")), "", self.prev_page
        )
        self.prev_action.setToolTip("Previous Page")
        self.next_action = self.toolbar.addAction(
            QIcon(str(IMAGES / "arrow_right.svg")), "", self.next_page
        )
        self.next_action.setToolTip("Next Page")
        self.toolbar.addAction(
            QIcon(str(IMAGES / "search.svg")), "", self.page_navigation
        )
        self.toolbar.addAction(QIcon(str(IMAGES / "zoom_in.svg")), "")
        self.toolbar.addAction(QIcon(str(IMAGES / "zoom_out.svg")), "")
        self.toolbar.addAction(QIcon(str(IMAGES / "bookmark_add.svg")), "")
        self.toolbar.addAction(QIcon(str(IMAGES / "comment_add.svg")), "")
        self.toolbar.addAction(
            QIcon(str(IMAGES / "one_page.svg")), "", self.set_one_page
        )
        self.toolbar.addAction(
            QIcon(str(IMAGES / "two_pages.svg")), "", self.set_double_page
        )
        self.analytics_action = self.toolbar.addAction(
            QIcon(str(IMAGES / "analytics.svg")), "", self.open_metadata_panel
        )
        self.analytics_action.setToolTip("Open Metadata Panel")

        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.toolbar)

        self.toolbar.show()

        self.image_label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.setCentralWidget(self.image_label)

        self.shortcut = QShortcut(QKeySequence("F11"), self)
        self.shortcut.activated.connect(self.toggle_fullscreen)

        self.display_current_page()

    def toggle_fullscreen(self) -> None:
        """
        Toggles fullscreen mode.
        """
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    def display_current_page(self) -> None:
        """
        Displays the current page by quering the sequence.

        If already in the image cache the image is loaded, otherwise
        a blank grey image with 'Loading...' is displayed and a
        task is scheduled which displays the image once completed.
        """
        display = self.sequence.current_display()
        self.preloader.preload(display)
        missing = [p for p in display if p not in self.preloader.image_cache]
        if missing:
            self.image_label.setText("Loading...")
            return

        if len(display) == 1:
            self.render_pixmap(self.preloader.image_cache[display[0]])
        else:
            self.render_pixmap(
                (
                    self.preloader.image_cache[display[0]],
                    self.preloader.image_cache[display[1]],
                )
            )

    @overload
    def render_pixmap(self, pixmap: QPixmap) -> None:
        """
        Renders a single image as the page for the reader.
        """
        ...

    @overload
    def render_pixmap(self, pixmap: tuple[QPixmap, QPixmap]) -> None:
        """
        Stiches together two images to display a double-page to the reader.
        """
        ...

    def render_pixmap(self, pixmap: QPixmap | tuple[QPixmap, QPixmap]) -> None:
        """
        Scales the pixmap taken from the image file into the right size and then
        displays it, finally updates the displayed page number. Stitching together two
        images if required.
        """
        if isinstance(pixmap, QPixmap):
            final = pixmap
            final = pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            left, right = pixmap
            page_width = max(1, self.image_label.width() // 2)
            page_height = self.image_label.height()

            left = left.scaled(
                page_width,
                page_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            right = right.scaled(
                page_width,
                page_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            width = left.width() + right.width()
            height = max(left.height(), right.height())

            final = QPixmap(width, height)
            final.fill(Qt.GlobalColor.transparent)

            painter = QPainter(final)
            painter.drawPixmap(0, (height - left.height()) // 2, left)
            painter.drawPixmap(left.width(), (height - right.height()) // 2, right)
            painter.end()

        self.image_label.setPixmap(final)
        # self.page_label.setText(f"Page {index + 1} / {self.comic.total_pages}")

    def on_page_ready(self, index: int):
        """
        Activated when the preloader loads an image.

        Checks that the loaded page is still needed for the view, and then
        calls the render function.

        Args:
            index (int): The index of the page just loaded by the preloader.
        """
        display = self.sequence.current_display()
        if index in display:
            self.display_current_page()

    def open_metadata_panel(self):
        """Opens the expanded metadata panel for the comic."""
        self.metadata_popup = MetadataDialog(self.comic.info)
        self.metadata_popup.show()

    def next_page(self):
        """
        Moves the reader to the next page.

        Tells the sequence to advance by 1 and then calls the function to display
        the current page.
        """
        self.sequence.next()
        self.display_current_page()

    def prev_page(self):
        """
        Moves the reader to the previous page.

        Tells the sequence to go back by 1 and then calls the function to display
        the current page.
        """
        self.sequence.prev()
        self.display_current_page()

    def keyPressEvent(self, event):
        """
        Listens for key presses of the right or left arrow and connects them to
        changing the page.
        """
        key = event.key()
        if key == Qt.Key.Key_Right:
            self.next_page()
        elif key == Qt.Key.Key_Left:
            self.prev_page()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """
        Listens for scroll wheel events from the mouse and connects these to
        the previous and next page functions.
        """
        angle = event.angleDelta().y()
        if angle > 0:
            self.next_page()
        elif angle < 0:
            self.prev_page()
        else:
            return

    def resizeEvent(self, event) -> None:
        """Redraws pixmap upon window resize."""
        super().resizeEvent(event)
        self.display_current_page()

    def set_one_page(self) -> None:
        """Sets the reading mode to single-page and refreshes the display."""
        self.sequence.set_mode(ReadMode.SINGLE_PAGE)
        self.display_current_page()

    def set_double_page(self) -> None:
        """Sets the reading mode to double-page and refreshes the display."""
        self.sequence.set_mode(ReadMode.DOUBLE_PAGE)
        self.display_current_page()

    def closeEvent(self, event) -> None:
        """
        Emits the closed signal when the reader is closed.

        This is used by the reading controller for memory and resource
        management.
        """
        self.preloader.pool.clear()
        self.closed.emit(self.comic.id, self.sequence.position_to_archive_index())
        super().closeEvent(event)

    def page_navigation(self) -> None:
        """
        Opens the comic navigation window and then updates the sequence
        with the new page, finally it refreshes the display.
        """
        dialog = Navigation(self.comic.total_pages)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.sequence.update_position(int(dialog.text))
            self.display_current_page()
        else:
            return

"""
A collection of classes for reading comics and preloading images so reading
is snappy and responsive.
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

from classes.helper_classes import GUIComicInfo
from metadata_gui_panel import MetadataDialog

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
    SINGLE_PAGE = auto()
    DOUBLE_PAGE = auto()


class PageType(Enum):
    UNKNOWN = auto()
    COVER = auto()
    BACK_COVER = auto()
    NORMAL = auto()
    SPREAD = auto()


@dataclass(slots=True)
class PageInfo:
    filename: str
    index: int
    page_type: PageType = PageType.UNKNOWN


@dataclass(slots=True)
class DisplayPage:
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
        page = self.pages[index]
        image_bytes = self.zip.read(page.filename)

        buffer = QBuffer()
        buffer.setData(QByteArray(image_bytes))
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)

        reader = QImageReader(buffer)
        size = reader.size()
        return size.width(), size.height()

    def analyse_page(self, page: PageInfo) -> PageInfo:
        if page.page_type != PageType.UNKNOWN:
            return page

        width, height = self.image_size(page.index)
        page.page_type = PageType.SPREAD if width / height > 1.3 else PageType.NORMAL
        return page


class ReadingSequence:
    def __init__(self, comic: Comic):
        super().__init__()
        self.comic = comic
        self.current_pos = 0
        self.display_pages: list[DisplayPage] = []
        self.page_to_position: dict[int, int] = {}
        i = 0
        while i < self.comic.total_pages:
            display = self.build_display_page(i)
            self.display_pages.append(display)
            pos = len(self.display_pages) - 1
            for page in display.pages:
                self.page_to_position[page] = pos

            if len(display.pages) == 2:
                i += 2
            else:
                i += 1

        self.current_pos = self.index_to_page(comic.current_index)

    def build_display_page(self, index: int) -> DisplayPage:
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

    def index_to_page(self, index: int) -> int:
        return self.page_to_position[index]

    def update_position(self, index: int):
        self.current_pos = self.index_to_page(index)

    def get_index_from_pos(self) -> int:
        display = self.display_pages[self.current_pos]
        return display.pages[0]

    def next(self):
        self.current_pos += 1

    def prev(self):
        self.current_pos -= 1

    def current_display(self) -> tuple[int, ...]:
        return self.display_pages[self.current_pos].pages


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

        buffer (int):
            Number of pages before and after the current page that should
            remain preloaded.

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
        safely through Qt's signal-slot system.
    """

    page_ready = Signal(int)
    spread_ready = Signal(int)

    def __init__(self, comic: Comic, buffer: int = 8):
        """
        Intialise the page preloader.

        Args:
            comic (Comic): Comic source for page image retrieval.
            buffer (int, optional): Number of pages before and after the
            current page that should remain cached and preloaded. Defaults to 8.
        """
        super().__init__()
        self.comic = comic
        self.buffer = buffer

        self.image_cache: dict[int, QPixmap] = {}
        self.loading: set[int] = set()
        self.wait_for_spread: bool = False
        self.pending_spread: tuple[int, int] | None = None

        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(5)

    def preload(self, index: int):
        """
        Preload pages surrounding the current reading position.

        This method determines which pages should remain based on
        the configured buffer size. Pages outside the desired range
        are evicted, and missing pages inside the range are scheduled
        for asynchronous loading.

        Args:
            current_index (int): Current page index around which
            preloading should occur.

        Notes:
            - Already cached pages are reused.
            - Pages currently loaded are not scheduled again.
            - Cache eviction occurs immediately for pages outside
            the preload window.
        """
        start = max(0, index - self.buffer)
        end = min(self.comic.total_pages - 1, index + self.buffer)
        self.pending_spread = (index, index + 1) if self.wait_for_spread else None

        wanted = set(range(start, end + 1))

        for idx in list(self.image_cache):
            if idx not in wanted:
                del self.image_cache[idx]

        for idx in wanted:
            if idx in self.image_cache or idx in self.loading:
                continue
            self.schedule_load(idx)

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

        The loaded pixmap is inserted into the cache and the page is
        marked as no longer loading.

        Args:
            index (int): Index of the loaded page.
            pixmap (QPixmap): Loaded page image.

        Emits:
            page_ready:
                Emitted after the image has been stored in the cache.
        """
        self.loading.discard(index)
        self.image_cache[index] = pixmap
        self.page_ready.emit(index)

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
        print(f"[ERROR] Failed to load page {index}: {message}")
        # TODO: Add retry method for pages that fail to load.
        # Need to implement some kind of diagnostic,
        # or at the minimum flag error to the user.


class Navigation(QDialog):
    def __init__(self, max_pages: int):
        super().__init__()

        layout = QVBoxLayout(self)
        instruct = QLabel(f"Enter page to navigate to. ({max_pages} pages)")
        self.line_edit = QLineEdit()
        self.line_edit.returnPressed.connect(self.accept)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(instruct)
        layout.addWidget(self.line_edit)
        layout.addWidget(buttons)

    @property
    def text(self) -> str:
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
    page_changed = Signal(str, int)

    def __init__(self, comic: Comic):
        """
        Creates the base window by opening the comic on the currenly read index
        and loading a certain amount of images before and after.

        Creates toolbars for comic navigation and commenting. These are not yet
        plugged into any slots.

        Args:
            comic (Comic): An instance of the :class`Comic` that gives useful data
                like unique identifier and current saved page from the database.
        """
        super().__init__()

        self.comic = comic
        self.sequence = ReadingSequence(self.comic)
        self.current_index: int = comic.current_index
        self.read_mode = ReadMode.SINGLE_PAGE  # default reading mode

        self.preloader = PagePreloader(self.comic, buffer=8)
        self.preloader.page_ready.connect(self.on_page_ready)
        self.preloader.spread_ready.connect(self.on_page_ready)

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
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    def display_current_page(self) -> None:
        """
        Displays the page with index `self.current_index`.

        If already in the image cache the image is loaded, otherwise
        a blank grey image with 'Loading...' is displayed and a
        task is scheduled which displays the image once completed.
        """
        if self.read_mode == ReadMode.SINGLE_PAGE:
            if self.current_index in self.preloader.image_cache:
                self.render_pixmap(
                    self.current_index, self.preloader.image_cache[self.current_index]
                )
            else:
                self.image_label.setText("Loading...")
                self.preloader.preload(self.current_index)
            return

        display = self.sequence.current_display()
        if len(display) == 1:
            index = display[0]
            logging.info(f"Changed page index to {index}")
            if index not in self.preloader.image_cache:
                self.image_label.setText("Loading...")
                self.preloader.preload(index)
                return
            self.render_pixmap(index, self.preloader.image_cache[index])

        else:
            left, right = display
            if (
                left in self.preloader.image_cache
                and right in self.preloader.image_cache
            ):
                left_img = self.preloader.image_cache[left]
                right_img = self.preloader.image_cache[right]
                self.render_pixmap(left, (left_img, right_img))
            else:
                self.image_label.setText("Loading...")
                self.preloader.preload(left)

    @overload
    def render_pixmap(self, index: int, pixmap: QPixmap) -> None: ...

    @overload
    def render_pixmap(self, index: int, pixmap: tuple[QPixmap, QPixmap]) -> None: ...

    def render_pixmap(
        self, index: int, pixmap: QPixmap | tuple[QPixmap, QPixmap]
    ) -> None:
        """
        Scales the pixmap taken from the image file into the right size and then
        displays it, finally updates the displayed page number.

        Args:
            index (int): The zero-indexed index of the page to scale and load around.
            pixmap (QPixmap): The QPixmap of the image to be displayed.
        """
        if isinstance(pixmap, QPixmap):
            final = pixmap
        else:
            left, right = pixmap

            width = left.width() + right.width()
            height = max(left.height(), right.height())

            final = QPixmap(width, height)
            final.fill(Qt.GlobalColor.transparent)

            painter = QPainter(final)
            painter.drawPixmap(0, 0, left)
            painter.drawPixmap(left.width(), 0, right)
            painter.end()

        scaled = final.scaledToHeight(
            self.image_label.height(), Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)
        self.page_label.setText(f"Page {index + 1} / {self.comic.total_pages}")

    def on_page_ready(self, index: int):
        """
        Activated when the preloader loads an image.

        Sets the current index to the loaded image index and renders
        the image.

        Args:
            index (int): The index of the page just loaded by the preloader.
        """
        if self.read_mode == ReadMode.SINGLE_PAGE:
            if index == self.current_index:
                self.display_current_page()
            return

        display = self.sequence.current_display()
        if index in display:
            self.display_current_page()

    def open_metadata_panel(self):
        """Opens the expanded metadata panel for the comic."""
        self.metadata_popup = MetadataDialog(self.comic.info)
        self.metadata_popup.show()

    def update_index(self):
        self.current_index = self.sequence.get_index_from_pos()

    def next_page(self):
        """
        Moves the reader to the next page.

        Increases the `self.current_index` by 1 and then calls the function to display
        the current page.
        """
        if self.read_mode == ReadMode.SINGLE_PAGE:
            if self.current_index + 1 < self.comic.total_pages:
                self.current_index += 1
                self.display_current_page()
        else:
            self.sequence.next()
            self.display_current_page()

    def prev_page(self):
        """
        Moves the reader to the previous page.

        Decreases the `self.current_index` by 1 and then calls the function to display
        the current page.
        """
        if self.read_mode == ReadMode.SINGLE_PAGE:
            if self.current_index > 0:
                self.current_index -= 1
                self.display_current_page()
        else:
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
        angle = event.angleDelta().y()
        if angle > 0:
            self.next_page()
        elif angle < 0:
            self.prev_page()
        else:
            return

    def set_one_page(self) -> None:
        self.read_mode = ReadMode.SINGLE_PAGE
        self.preloader.wait_for_spread = False
        self.update_index()
        self.display_current_page()

    def set_double_page(self) -> None:
        self.read_mode = ReadMode.DOUBLE_PAGE
        self.preloader.wait_for_spread = True
        self.sequence.update_position(self.current_index)
        self.display_current_page()

    def closeEvent(self, event) -> None:
        """
        Emits the closed signal when the reader is closed.

        This is used by the reading controller for memory and resource
        management.
        """
        self.update_index()
        self.closed.emit(self.comic.id, self.current_index)
        super().closeEvent(event)

    def page_navigation(self) -> None:
        dialog = Navigation(self.comic.total_pages)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_index = int(dialog.text)
            self.sequence.update_position(self.current_index)
            self.display_current_page()
        else:
            return

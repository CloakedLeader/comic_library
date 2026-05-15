import logging
import zipfile
from collections import OrderedDict
from functools import partial
from io import BytesIO

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QToolBar,
    QToolButton,
    QWidget,
)

from classes.helper_classes import GUIComicInfo
from metadata_gui_panel import MetadataDialog

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
            if name.lower().endswith(
                (".jpg", ".jpeg", ".png")
            )  # TODO: Use sort_function.py here.
        )
        if not self.image_names:
            raise ComicError("No images found in the file.")
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

        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(4)

    def preload(self, current_index: int):
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
        start = max(0, current_index - self.buffer)
        end = min(self.comic.total_pages - 1, current_index + self.buffer)

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


class SimpleReader(QMainWindow):
    closed = Signal(str, int)
    page_changed = Signal(str, int)

    def __init__(self, comic: Comic):
        super().__init__()

        self.comic = comic
        self.current_index: int = comic.current_index

        self.preloader = PagePreloader(self.comic, buffer=2)
        self.preloader.page_ready.connect(self.on_page_ready)

        self.setWindowTitle("Comic Reader")

        self.image_label = QLabel("Loading...", alignment=Qt.AlignmentFlag.AlignCenter)
        self.page_label = QLabel("Page 1", alignment=Qt.AlignmentFlag.AlignCenter)

        self.menu_bar_widget = QWidget()
        self.menu_bar_layout = QHBoxLayout()
        self.menu_bar_widget.setLayout(self.menu_bar_layout)
        self.setMenuWidget(self.menu_bar_widget)

        self.add_menu_button("Navigation Toolbar", self.show_navigation_toolbar)
        self.add_menu_button("Comments Toolbar", self.show_comments_toolbar)
        self.add_menu_button("Metadata", self.open_metadata_panel)
        # self.add_menu_button("Settings", self.open_settings_panel)
        # self.add_menu_button("Help", self.open_help_panel)

        self.menu_bar_widget.hide()
        self.hide_menu_timer = QTimer()
        self.hide_menu_timer.setSingleShot(True)
        self.hide_menu_timer.timeout.connect(self.menu_bar_widget.hide)

        self.setMouseTracking(True)

        self.navigation_toolbar = QToolBar("Navigation Tools")
        self.navigation_toolbar.addAction("Zoom In")
        self.navigation_toolbar.addAction("Zoom Out")
        self.navigation_toolbar.addAction("Prev Page", self.prev_page)
        self.navigation_toolbar.addAction("Next Page", self.next_page)

        self.comments_toolbar = QToolBar("Commenting Tools")
        self.comments_toolbar.addAction("Add Bookmark")
        self.comments_toolbar.addAction("Add Comment")

        self.addToolBar(self.navigation_toolbar)
        self.addToolBar(self.comments_toolbar)

        self.navigation_toolbar.show()
        self.comments_toolbar.hide()
        self.current_toolbar = self.navigation_toolbar

        self.image_label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCentralWidget(self.image_label)

        self.display_current_page()

    def display_current_page(self) -> None:
        index = self.current_index
        logging.info(f"Changed page index to {index}")
        if index in self.preloader.image_cache:
            self.render_pixmap(index, self.preloader.image_cache[index])
        else:
            self.image_label.setText("Loading...")
            self.preloader.preload(index)

        # scaled = pixmap.scaledToHeight(
        #     self.image_label.height(), Qt.SmoothTransformation
        # )
        # self.image_label.setPixmap(scaled)
        # self.page_label.setText(f"Page {index + 1} / {self.comic.total_pages}")

        # if index + 1 < self.comic.total_pages:
        #     self.preload_page(index + 1)

    def render_pixmap(self, index: int, pixmap: QPixmap) -> None:
        scaled = pixmap.scaledToHeight(
            self.image_label.height(), Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)
        self.page_label.setText(f"Page {index + 1} / {self.comic.total_pages}")

        self.preloader.preload(index)

    def on_page_ready(self, index: int):
        if index == self.current_index:
            pixmap = self.preloader.image_cache.get(index)
            if pixmap:
                self.render_pixmap(index, pixmap)

    def add_menu_button(self, name: str, callback, *args):
        button = QToolButton()
        button.setText(name)
        button.setAutoRaise(True)
        button.clicked.connect(partial(callback, *args))
        self.menu_bar_layout.addWidget(button)

    def switch_toolbar(self, toolbar: QToolBar):
        if self.current_toolbar == toolbar:
            return
        self.current_toolbar.hide()
        toolbar.show()
        self.current_toolbar = toolbar

    def show_navigation_toolbar(self):
        self.switch_toolbar(self.navigation_toolbar)

    def show_comments_toolbar(self):
        self.switch_toolbar(self.comments_toolbar)

    def open_metadata_panel(self):
        self.metadata_popup = MetadataDialog(self.comic.info)
        self.metadata_popup.show()

    # def resizeEvent(self, event):
    #     self.preload_page(self.current_index)

    def next_page(self):
        if self.current_index + 1 < self.comic.total_pages:
            self.current_index += 1
            self.display_current_page()
            self.page_changed.emit(self.comic.id, self.current_index)

    def prev_page(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.display_current_page()
            self.page_changed.emit(self.comic.id, self.current_index)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Right:
            self.next_page()
        elif key == Qt.Key.Key_Left:
            self.prev_page()

    def mouseMoveEvent(self, event):
        mouse_y = event.position().y()

        if mouse_y <= 40:
            if not self.menu_bar_widget.isVisible():
                self.menu_bar_widget.show()
            self.hide_menu_timer.stop()

        else:
            if self.menu_bar_widget.isVisible() and not self.hide_menu_timer.isActive():
                self.hide_menu_timer.start(1500)
        super().mouseMoveEvent(event)

    def closeEvent(self, event) -> None:
        self.closed.emit(self.comic.id, self.current_index)
        super().closeEvent(event)

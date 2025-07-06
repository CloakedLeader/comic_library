import zipfile
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QMainWindow, QHBoxLayout,QHBoxLayout, QToolButton, QToolBar, QDialog
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from typing import Any
import os
import sys
import re
from PIL import Image
from io import BytesIO
from collections import OrderedDict
from functools import partial

from metadata_gui_panel import MetadataDialog
from reader import Comic, SimpleReader

class ReadingController:
    """Controller for managing comic reading sessions and reader windows.
        """Initialize the reading controller.
        
        Args:
            comic: Dictionary containing comic information including 'filepath' key
        """
    
    This class handles the creation and management of comic reader instances,
    allowing multiple comics to be read simultaneously. It maintains a list
        """Open a new comic reader window.
        
        Creates a Comic instance from the stored filepath, instantiates a SimpleReader,
        displays the reader window, and tracks it in the open windows list for management.
        """
    of open reader windows and provides functionality to close them all at once.
    """
    def __init__(self, comic: dict[str, Any]) -> None:
        """Close all open reader windows and clear the tracking list.
        
        This method iterates through all currently open comic reader windows,
        closes them, and clears the internal list of open windows.
        """
        self.filepath = comic.get("filepath")
        self.open_windows: list[SimpleReader] = []
    
    def read_comic(self) -> None:
        comic_data = Comic(self.filepath)
        comic_reader = SimpleReader(comic_data)
        comic_reader.show()
        self.open_windows.append(comic_reader)
        
    def close_all_windows(self) -> None:
        for window in self.open_windows:
            window.close()
        self.open_windows.clear()
        
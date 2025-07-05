import zipfile
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QMainWindow, QHBoxLayout,QHBoxLayout, QToolButton, QToolBar, QDialog
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from typing import Dict, List, Any
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
    def __init__(self, comic: Dict[str, Any]) -> None:
        self.filepath = comic.get("filepath")
        self.open_windows: List[SimpleReader] =[]
    
    def read_comic(self) -> None:
        comic_data = Comic(self.filepath)
        comic_reader = SimpleReader(comic_data)
        comic_reader.show()
        self.open_windows.append(comic_reader)
        
    def close_all_windows(self) -> None:
        for window in self.open_windows:
            window.close()
        self.open_windows.clear()
        
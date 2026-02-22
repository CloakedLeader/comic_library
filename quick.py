from metadata_controller import MetadataController
from main import HomePage
from pathlib import Path
import uuid
from PySide6.QtWidgets import QApplication
import sys
from qasync import QEventLoop
import asyncio


qt_app = QApplication(sys.argv)
loop = QEventLoop(qt_app)
asyncio.set_event_loop(loop)
asyncio.get_event_loop().set_debug(False)

home = HomePage()
single_proc = MetadataController(str(uuid.uuid4()), Path("G:/adams-comics/1 - Marvel Comics/Quicksilver - No Surrender TPB #01 (Nov 2018).cbz"), home)
single_proc.process()
import requests
import os
import zipfile
import xml.etree.ElementTree as ET
import sqlite3
from typing import Optional, Union, Tuple, List
from fuzzywuzzy import fuzz
import sys
import time
import re
from word2number import w2n
from dotenv import load_dotenv

api_key = os.getenv("API_KEY")



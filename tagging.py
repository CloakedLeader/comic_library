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

api_key = "61d8fd6e7cc37cc177cd09f795e9c585999903ed"



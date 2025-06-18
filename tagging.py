import requests
import os
import xml.etree.ElementTree as ET
from typing import Optional, Union, Tuple, List
from word2number import w2n
from dotenv import load_dotenv
from rapidfuzz import fuzz
from PIL import Image
import imagehash
from concurrent.futures import ThreadPoolExecutor
import zipfile
import xml.etree.ElementTree as ET
import sqlite3
from fuzzywuzzy import fuzz
import sys
import re
from pathlib import Path
from io import BytesIO
import json


load_dotenv()

api_key = os.getenv("API_KEY")



def sort_imgs(filename: str) -> Optional[int]:
    numbers = re.findall(r'\d+', filename)
    return int(numbers[-1]) if numbers else -1

class RequestData:
    
    def __init__( self, name: str, issue_num: int, pub_year: int, publisher: str = None, start_year: int = None ):
        self.unclean_title = name
        self.num = issue_num
        self.start_year = start_year
        self.pub_year = pub_year
        self.publisher = publisher

header = {
    "User-Agent": "AutoComicLibrary/1.0 (contact: adam.perrott@protonmail.com; github.com/CloakedLeader/comic_library)",
    "Accept": r"*/*",
    "Accept-Encoding": "gzip,deflate,br",
    "Connection": "keep-alive"
}
session = requests.Session()
session.headers.update(header)


class HttpRequest:

    base_address = f"https://comicvine.gamespot.com/api"
    
    def __init__( self, data: RequestData ):
        self.data = data
        self.payload = self.create_info_dict()
        


    def create_info_dict( self ):
        payload = {}
        payload["api_key"] = api_key
        payload["resources"] = "volume"
        payload["field_list"] = "id,image,publisher,name,start_year,date_added"
        payload["format"] = "json"
        payload["query"] = self.data.unclean_title
        payload["limit"] = 50
        return payload

    def build_url_search( self ):
        req = requests.Request(
            method="GET",
            url=f"{HttpRequest.base_address}/search/",
            params=self.payload,
            headers=header
        )
        prepared = req.prepare()
        self.url_search = prepared.url
        print(self.url_search)

    def build_url_iss( self, id: int ):
        req = requests.Request(
            method="GET",
            url=f"{HttpRequest.base_address}/issues/",
            params={
                "api_key" : api_key,
                "format" : "json",
                "filter" : f"volume:{id}"
            }
        )
        prepared = req.prepare()
        self.url_iss = prepared.url
        print(self.url_iss)
    
    def get_request( self, type: str ):
        if type == "search": 
            if not hasattr(self, "url_search"):
                raise RuntimeError("You must build url before sending request.")
            response = session.get(self.url_search)
            if response.status_code != 200:
                print(f"Request failed with status code: {response.status_code}")
                print(response.text)
            data = response.json()

        elif type == "iss":
            if not hasattr(self, "url_iss"):
                raise RuntimeError("You must build url before sending request.")
            response = session.get(self.url_iss)
            if response.status_code != 200:
                print(f"Request failed with status code: {response.status_code}")
                print(response.text)
            data = response.json()

        else:
            print("Need to specify which database to search in.")
        if data["error"] != "OK" or data["number_of_total_results"] == 0:
                print("Error, please investigate")
                return
        # Want to tell the user to manually tag the comic.
        return data
    
    def download_img( self, url ):
        try:
            response = requests.get(url)
            response.raise_for_status()
            image = (BytesIO(response.content))
            return image
        except Exception as e:
            print(f"Failed to process {url}: {e}")
            return None

    

class ResponseValidator:


    def __init__( self, response: dict, expected_data: RequestData ):
        self.results = response["results"]
        self.expected_info = expected_data

    def filter_results( self, predicate):
        return [item for item in self.results if predicate(item)]

    def year_checker( self ):
        def check_year(item):
            year = int(item["date_added"][:4])
            return abs( year - self.expected_info.pub_year ) <= 3
        return self.filter_results(check_year)
    
    @staticmethod
    def fuzzy_match( a, b, threshold=60 ):
        return fuzz.token_sort_ratio( a, b ) >= threshold

    def title_checker( self ):
        def check_title(item):
            title = item["name"]
            return self.fuzzy_match(title, self.expected_info.unclean_title)
        return self.filter_results(check_title)

    
    def pub_checker( self, results ):
        foriegn_keywords = {"panini", "norma"}
        english_publishers = {
            "Marvel": 31,
            "DC Comics": 10,
            "Image": 513,
            "IDW Publishing": 1190,
            "Dark Horse Comics": 364 
            }
        
        filtered = []
        for result in results:
            pub_dict = result["publisher"]
            pub_id = pub_dict["id"]
            pub_name = pub_dict["name"]
            if pub_id in english_publishers.values():
                filtered.append(result)
            elif pub_name.split() in foriegn_keywords:
                print(f"Filtered out {pub_name} due to foreign publisher.")
            else:
                filtered.append(result)
                print(f"Accepted '{pub_name}' but please check to see if they need adding to foriegn publishers.")
        return filtered

           
    
    def cover_img_url_getter( self, filtered_results ):
        self.urls = []
        for i in filtered_results:
            self.urls.append(i["image"]["thumb_url"])

    def cover_img_comparison( self, known_image_bytes, unsure_image_bytes, threshold=6) -> bool: # Returns true if it finds match.
        known_image = Image.open(known_image_bytes)
        unsure_image = Image.open(unsure_image_bytes)
        hash1 = imagehash.phash(known_image)
        hash2 = imagehash.phash(unsure_image)
        hash_diff = hash1 - hash2
        print(f"[DEBUG] Hashing distance = {hash_diff}, threshold = {threshold}")
        return hash_diff <= threshold

class TaggingPipeline:
    def __init__( self, data: RequestData, path: str, size: float ):
        self.data = data
        self.path = path
        self.size = size
        self.http = HttpRequest(data)
        self.validator = None
        self.cover = self.cover_getter()

    def cover_getter( self ):
        with zipfile.ZipFile(self.path, 'r') as zip_ref:
            image_files = [f for f in zip_ref.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            if not image_files:
                print("Empty archive.")
                return
            image_files.sort(key=sort_imgs)
            cover = zip_ref.read(image_files[0])
            return BytesIO(cover)

    def run( self ):
        self.http.build_url_search()
        results = self.http.get_request("search")
        self.validator = ResponseValidator( results, self.data )

        print(f"There are {len(results)} results returned from HTTP query.")
        results = self.validator.year_checker()
        self.validator.results = results
        results = self.validator.title_checker()
        self.validator.results = results
        # some way to tell the user to manually tag, or give them options to choose from
        
        print(f"After filtering for title and year,there are {len(results)} remaining matches.")
        if len(results) != 0:
            self.validator.cover_img_url_getter(results)
            images = []
            with ThreadPoolExecutor(max_workers=5) as executor:
                images = list(executor.map(self.http.download_img, self.validator.urls))
            matches_indices = []
            for index, i in enumerate(images):
                result = self.validator.cover_img_comparison(self.cover, i)
                print(f"Index {index}: match result = {result}")
                if result:
                    matches_indices.append(index)
            final_results = []
            final_results = [results[i] for i in matches_indices]
        final_results = self.validator.pub_checker(final_results)

        if len(final_results) == 1:
            print("BINGO - ONE RESULT")
            self.match_bool = True
            self.match = final_results[0]
            self.vol_id = self.match["id"]
            print(f"Volume id is: {self.vol_id}")
            print(self.match)
        elif len(final_results) > 1:
            print(f"Too many matches, {len(final_results)} to be specific")
            print(final_results)
            # This is where the user needs to manually select.
            return
        elif len(final_results) == 0:
            print("No matches")
            #No matches, need to implement logic here to deal with that.
            return 
        
        self.http.build_url_iss(self.vol_id)
        results2 = self.http.get_request("iss")
        self.validator2 = ResponseValidator( results2, self.data )
        print(f"There are {len(self.validator2.results)} results matching the id.")
        if len(self.validator2.results) == 1 and self.validator2.results["cover_date"][:4] == self.data.pub_year:
            print("Bingo - Only one collection in this volume, must be the correct one.")
            self.iss_id = self.validator2.results["id"]


        elif len(self.validator2.results) == 0:
            pass
        elif len(self.validator2.results) > 1:
            pass

        



    
    
    

        
hu = RequestData("Juggernaut - No Stopping Now", 1, 2021)
da = TaggingPipeline(hu, r"D:\comic_library\Juggernaut - No Stopping Now TPB (March 2021).cbz", 500)
ad = da.run()

        

# with open("comicvine_results2.json", "w", encoding="utf-8") as f:
#     json.dump( ad, f, indent=2)


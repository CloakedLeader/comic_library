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
import time

start_time = time.time()

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
        if data["error"] != "OK":
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

    issue_threshold = 80
    volume_threshold = 65


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
    def fuzzy_match( a, b, threshold=65 ):
        return fuzz.token_sort_ratio( a, b ) >= threshold

    def title_checker( self ):
        def check_title(item):
            used_fallback = False
            ambig_names = ["tpb", "hc", "omnibus"]
            ambig_regexes = [
                r"^vol(?:ume)?\.?\s*\d+$", # matches "vol. 1", "volume 2", "vol 3"
                r"^#\d+$", # matches "#1", "#12" etc
                r"^issue\s*\d+$" # matches "issue 3"
            ]
            title = item["name"]
            if title:
                lowered_title = title.lower().strip()
                is_ambig = (
                    lowered_title in ambig_names or 
                    any(re.match(p, lowered_title) for p in ambig_regexes) 
                )
                if is_ambig:
                    title = item.get("volume", {}).get("name")
                    used_fallback = True
            else:
                title = item.get("volume", {}).get("name")
                used_fallback = True
            if title is None:
                return False
            threshold = ResponseValidator.volume_threshold if used_fallback else ResponseValidator.issue_threshold
            return self.fuzzy_match(title, self.expected_info.unclean_title, threshold=threshold)
        return self.filter_results(check_title)

    def vol_title_checker( self ):
        def check_title(item):
            title = item["name"]

    
    def pub_checker( self, results: list ):
        foriegn_keywords = {"panini", "verlag", "norma", "televisa", "planeta", "deagostini"}
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
            elif any(word.lower() in foriegn_keywords for word in pub_name.split()):
                print(f"Filtered out {pub_name} due to foreign publisher.")
            else:
                filtered.append(result)
                print(f"Accepted '{pub_name}' but please check to see if they need adding to foriegn publishers.")
        return filtered

    
    def cover_img_url_getter( self, filtered_results ):
        self.urls = []
        for i in filtered_results:
            self.urls.append(i["image"]["thumb_url"])


    def cover_img_comparison( self, known_image_hash, unsure_image_bytes, threshold=8) -> bool: # Returns true if it finds match.
        unsure_image = Image.open(unsure_image_bytes)
        hash1 = known_image_hash
        hash2 = imagehash.phash(unsure_image)
        hash_diff = hash1 - hash2
        print(f"[DEBUG] Hashing distance = {hash_diff}, threshold = {threshold}")
        return hash_diff <= threshold
    
    def cover_img_comp_w_weight( self, known_image_hashes, unsure_image_bytes, max_dist=64):
        weights = {
            "phash" : 0.6,
            "dhash" : 0.2,
            "ahash" : 0.2
        }
        unsure_hashes = {
            "phash" : imagehash.phash(unsure_image_bytes),
            "dhash" : imagehash.dhash(unsure_image_bytes),
            "ahash" : imagehash.average_hash(unsure_image_bytes)
        }
        score = 0.0
        for key in weights:
            dist = known_image_hashes[key] - unsure_hashes[key]
            normalised = 1 - (dist / max_dist)
            score += weights[key] * normalised
        return score
    


class TaggingPipeline:
    def __init__( self, data: RequestData, path: str, size: float ):
        self.data = data
        self.path = path
        self.size = size
        self.http = HttpRequest(data)
        self.validator = None
        self.cover = self.cover_getter()
        self.coverhashes = self.cover_hasher() # dictionary of (phash, dhash, ahash)

    def cover_getter( self ):
        with zipfile.ZipFile(self.path, 'r') as zip_ref:
            image_files = [f for f in zip_ref.namelist() if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            if not image_files:
                print("Empty archive.")
                return
            image_files.sort()
            cover = zip_ref.read(image_files[0])
            deb = Image.open(BytesIO(cover))
            deb.show()
            return BytesIO(cover)
    
    def cover_hasher( self ):
        image = Image.open(self.cover)
        return {
            "phash" : imagehash.phash(image),
            "dhash" : imagehash.dhash(image),
            "ahash" : imagehash.average_hash(image)
        }

        
    def ask_user(self, results: list):
        pass
    

    def run( self ):
        self.http.build_url_search()
        results = self.http.get_request("search")
        self.validator = ResponseValidator( results, self.data )

        print(f"There are {len(results["results"])} results returned from HTTP query.")
        results = self.validator.title_checker()
        self.validator.results = results
        results = self.validator.pub_checker(results)
        self.validator.results = results
        print(f"After filtering for title and publisher, there are {len(results)} remaining matching volumes.")
        final_results = results

        if len(final_results) == 0:
            # No results - need to come up with logic/a solution here.
            pass
        
        print(f"There are {len(final_results)} volumes to check")
        vol_info = []
        for i in final_results:
            id = i["id"]
            name = i["name"]
            vol_info.append((id, name))
        good_matches = []
        skipped_vols = []
        for j, k in vol_info:
            self.http.build_url_iss(j)
            temp_results = self.http.get_request("iss")

            self.temp_validator = ResponseValidator( temp_results, self.data )
            print(f"There are {len(self.temp_validator.results)} issues in the matching volume: '{k}'.")
            temp_results = self.temp_validator.year_checker()
            self.temp_validator.results = temp_results
            temp_results = self.temp_validator.title_checker()
            self.temp_validator.results = temp_results

            print(f"After filtering for title and year there are {len(temp_results)} results remaining.")
            if len(temp_results) != 0:
                if len(temp_results) > 25:
                    print(f"Too many issues to compare covers, skipping volume '{k}'.")
                    skipped_vols.append((j, k, len(temp_results)))
                    continue
                self.temp_validator.cover_img_url_getter(temp_results)
                images =[]
                with ThreadPoolExecutor(max_workers=5) as executor:
                    images = list(executor.map(self.http.download_img, self.temp_validator.urls))
                matches_indices = []
                for index, i in enumerate(images):
                    if i is None:
                        continue
                    try:
                        img_pil = Image.open(i)
                        score = self.temp_validator.cover_img_comp_w_weight(self.coverhashes, img_pil)
                        print(f"Index {index}: similarity score = {score:.2f}")
                        if score > 0.85:
                            matches_indices.append(index)
                    except Exception as e:
                        print(f"Error comparing image at index {index}: {e}.")
                final_results = [temp_results[i] for i in matches_indices]
                good_matches.extend(final_results)
            else:
                continue

        if len(good_matches) == 1:
            print(good_matches[0]["volume"]["name"])
            print("There is ONE match!!!")
            return good_matches
        elif len(good_matches) == 0:
            print("There are no matches.")
            #If there is no matches need to do something. Perhaps the comic is new and hasnt been uploaded onto comicvine properly.
        elif len(good_matches) > 1:
            for i in good_matches:
                print(i["volume"]["name"])
            print(f"FINAL COUNT: There are {len(good_matches)} remaining matches.")    
            #Need to use scoring or sorting or closest title match etc.
            #If that cant decide then we need to flag the comic and ask the user for input.

        
    
hu = RequestData("East of West", 2, 2014)
da = TaggingPipeline(hu, r"D:\Comics\Indie\Hickman\East of West\East of West TPB #02 We Are All One (2014).cbz", 500)
ad = da.run()

for i in range(1000000):
    pass
end_time = time.time()
print(f"Execution time: {end_time - start_time:.4f} seconds")
        
# with open("comicvine_results3.json", "w", encoding="utf-8") as f:
#     json.dump( ad, f, indent=2)
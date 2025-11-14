from io import BytesIO

import requests


header = {
    "User-Agent": "AutoComicLibrary/1.0 (contact: adam.perrott@protonmail.com;"
    " github.com/CloakedLeader/comic_library)",
    "Accept": r"*/*",
    "Accept-Encoding": "gzip,deflate,br",
    "Connection": "keep-alive",
}


class RequestData:

    def __init__(
        self,
        issue_num: int,
        year: int,
        series: str,
        title: str,
        publisher: str | None = None,
    ):
        self.series = series
        self.title = title
        self.unclean_title = (series or "") + (title or "")
        self.num = issue_num
        self.pub_year = year
        self.publisher = publisher or ""



class HttpRequest:

    base_address = "https://comicvine.gamespot.com/api"

    def __init__(self, data: RequestData, api_key: str, session):
        self.data = data
        self.api_key = api_key
        self.session = session
        self.payload = self.create_info_dict(self.data.unclean_title)

    def create_info_dict(self, query):
        payload = {}
        payload["api_key"] = self.api_key
        payload["resources"] = "volume"
        payload["field_list"] = (
            "id,image,publisher,name,start_year,date_added,"
            "count_of_issues,description,last_issue"
        )
        payload["format"] = "json"
        payload["limit"] = 50
        return payload

    def build_url_search(self, query: str):
        payload = self.payload.copy()
        payload["query"] = query
        req = requests.Request(
            method="GET",
            url=f"{HttpRequest.base_address}/search/",
            params=payload,
            headers=header,
        )
        prepared = req.prepare()
        self.url_search = prepared.url
        print(self.url_search)

    def build_url_iss(self, id: int):
        req = requests.Request(
            method="GET",
            url=f"{HttpRequest.base_address}/issues/",
            params={
                "api_key": self.api_key,
                "format": "json",
                "filter": f"volume:{id}",
            },
        )
        prepared = req.prepare()
        self.url_iss = prepared.url
        print(self.url_iss)

    def get_request(self, type: str):
        if type == "search":
            if not hasattr(self, "url_search"):
                raise RuntimeError("You must build url before sending request.")
            if self.url_search is None:
                raise ValueError("search url cannot be None")
            response = self.session.get(self.url_search)
            if response.status_code != 200:
                print(
                    f"Request failed with status code: \
                      {response.status_code}"
                )
                print(response.text)
            data = response.json()

        elif type == "iss":
            if not hasattr(self, "url_iss"):
                raise RuntimeError("You must build url before sending request.")
            if self.url_iss is None:
                raise ValueError("issue url cannot be None")
            response = self.session.get(self.url_iss)
            if response.status_code != 200:
                print(
                    f"Request failed with status code: \
                      {response.status_code}"
                )
                print(response.text)
            data = response.json()

        else:
            print("Need to specify which database to search in.")
        if data["error"] != "OK":
            print("Error, please investigate")
            return
        # Want to tell the user to manually tag the comic.
        return data

    def download_img(self, url):
        try:
            response = requests.get(url, timeout=3000)
            response.raise_for_status()
            image = BytesIO(response.content)
            return image
        except Exception as e:
            print(f"Failed to process {url}: {e}")
            return None
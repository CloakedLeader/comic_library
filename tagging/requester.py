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
        """
        Initialise RequestData with metadata describing a comic issue.
        
        Parameters:
        	issue_num (int): Issue number for the comic.
        	year (int): Publication year of the issue.
        	series (str): Series name.
        	title (str): Issue title.
        	publisher (str | None): Publisher name; stored as empty string if None.
        """
        self.series = series
        self.title = title
        self.unclean_title = (series or "") + (title or "")
        self.num = issue_num
        self.pub_year = year
        self.publisher = publisher or ""



class HttpRequest:

    base_address = "https://comicvine.gamespot.com/api"

    def __init__(self, data: RequestData, api_key: str, session):
        """
        Initialises an HttpRequest configured to query the Comic Vine API.
        
        Stores the provided request metadata and API key, retains the HTTP session, and prebuilds the search payload from the request data's `unclean_title`.
        
        Parameters:
            data (RequestData): Issue and series metadata used to construct queries.
            api_key (str): API key used for authenticated requests.
        """
        self.data = data
        self.api_key = api_key
        self.session = session
        self.payload = self.create_info_dict(self.data.unclean_title)

    def create_info_dict(self, query):
        """
        Builds the base payload dictionary used for Comic Vine API requests.
        
        Parameters:
        	query (str): Provided query string (currently ignored by this function).
        
        Returns:
        	dict: Payload containing:
        	- `api_key`: API key string from the HttpRequest instance.
        	- `resources`: set to `"volume"`.
        	- `field_list`: comma-separated fields requested (`"id,image,publisher,name,start_year,date_added,count_of_issues,description,last_issue"`).
        	- `format`: set to `"json"`.
        	- `limit`: integer limit of `50`.
        """
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
        """
        Builds and stores the prepared API search URL for a given query.
        
        Sets the instance attribute `url_search` to the fully prepared search URL and prints that URL.
        
        Parameters:
            query (str): Search string to include in the request parameters.
        """
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
        """
        Builds and stores a prepared Comic Vine API URL for querying issues belonging to a specific volume.
        
        Parameters:
            id (int): The Comic Vine volume identifier used in the request filter; stored URL is for the /issues/ endpoint filtered by this volume. The constructed URL is saved to `self.url_iss` and printed.
        """
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
        """
        Execute a prepared GET request against the Comic Vine search or issues endpoint and return the parsed JSON response.
        
        Parameters:
        	type (str): Either `"search"` to use the previously built search URL or `"iss"` to use the previously built issues URL.
        
        Returns:
        	dict | None: Parsed JSON response dictionary when the API `error` field equals `"OK"`, `None` if the API reports an error or an unsupported `type` was provided.
        
        Raises:
        	RuntimeError: If the required URL (search or issue) has not been built on the instance.
        	ValueError: If the required URL attribute exists but is `None`.
        """
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
        """
        Download an image from the given URL and return it as an in-memory binary stream.
        
        Parameters:
            url (str): URL of the image to download.
        
        Returns:
            BytesIO | None: A BytesIO containing the image bytes on success, `None` if the download or processing fails.
        """
        try:
            response = requests.get(url, timeout=3000)
            response.raise_for_status()
            image = BytesIO(response.content)
            return image
        except Exception as e:
            print(f"Failed to process {url}: {e}")
            return None
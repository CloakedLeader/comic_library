from io import BytesIO
import logging
import requests

from classes.helper_classes import APIResults


logging.basicConfig(
    filename="debug.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


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
    ) -> None:
        """
        Initialise RequestData with metadata describing a comic.

        Args:
            issue_num (int): Issue number for the comic.
            year (int): Publication year of the issue.
            series (str): Series name.
            title (str): Comic title.
            publisher (str | None, optional): Publisher name. Defaults to None.
        """

        self.series = series
        self.title = title
        self.unclean_title = (series or "") + (title or "")
        self.num = issue_num
        self.pub_year = year
        self.publisher = publisher or ""


class HttpRequest:
    base_address = "https://comicvine.gamespot.com/api"

    def __init__(
        self, data: RequestData, api_key: str, session: requests.Session
    ) -> None:
        """
        Initialises an HTTPRequest configured to query the ComicVine API.

        Stores the provided request metadata and API key, retains the HTTP session
        and prebuilds the search payload.

        Args:
            data (RequestData): Issue and series metadata used to construct queries.
            api_key (str): API key used for API calls.
            session (requests.Session): The HTTP session to be used by instance methods.
        """
        self.data = data
        self.api_key = api_key
        self.session = session
        self.payload: dict[str, str | int] = {}
        self.payload["api_key"] = self.api_key
        self.payload["limit"] = 50
        self.payload["resources"] = "volume"
        self.payload["field_list"] = (
            "id,image,publisher,name,start_year,date_added,"
            "count_of_issues,description,last_issue"
        )
        self.payload["format"] = "json"

    def build_url_search(self, query: str) -> None:
        """
        Builds and stores the prepared API search URL for a given query.

        Sets the instance attribute 'url_search' to the fully prepared search URL
        and prints that URL.

        Args:
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
        logging.info(f"The search URL is: {self.url_search}")

    def build_url_iss(self, id: int) -> None:
        """
        Builds and stores a prepared ComicVine API URL for querying issues belonging to
        a specific volume.

        Args:
            id (int): The ComicVine volume identifier used in the request filter.
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
        logging.info(f"The issue URL is: {self.url_iss}")

    def get_request(self, request_type: str) -> APIResults:
        """
        Execute  a prepared GET request against the ComicVine API and return
        the parsed JSON.

        Args:
            request_type (str): Either "search" or "iss" to use one of the two
                previously built URL's.

        Raises:
            RuntimeError: If the required URL has not been build for the instance.
            ValueError: If the required URL attribute exists but its value is None.

        Returns:
            dict | None: Parsed JSON response dictionary when the API 'error' field is
                "OK". None if the API reports an error or invalid request syntax.
        """

        if request_type == "search":
            if not hasattr(self, "url_search"):
                raise RuntimeError("You must build url before sending request.")
            if self.url_search is None:
                raise ValueError("search url cannot be None")
            response = self.session.get(self.url_search)
            if response.status_code != 200:
                logging.warning(
                    f"Search request failed with status code: \
                      {response.status_code}"
                )
                logging.warning("\n" + response.text)
            data = response.json()

        elif request_type == "iss":
            if not hasattr(self, "url_iss"):
                raise RuntimeError("You must build url before sending request.")
            if self.url_iss is None:
                raise ValueError("issue url cannot be None")
            response = self.session.get(self.url_iss)
            if response.status_code != 200:
                logging.warning(
                    f"Issue request failed with status code: \
                      {response.status_code}"
                )
                logging.warning("\n" + response.text)
            data = response.json()

        else:
            raise ValueError(f"Unknown request type: {request_type!r}")
        if data["error"] != "OK":
            logging.warning("Error, please investigate")
            return None
        # Want to tell the user to manually tag the comic.
        return data
            raise RuntimeError("Error, please investigate")
        return self.format_api_results(data)

    @staticmethod
    def format_api_results(complete_results: dict) -> APIResults:
        return APIResults(
            error=complete_results["error"],
            limit=complete_results["limit"],
            offset=complete_results["offset"],
            result_per_page=complete_results["number_of_page_results"],
            total_results=complete_results["number_of_total_results"],
            status_code=complete_results["status_code"],
            results=complete_results["results"],
        )

    def download_img(self, url: str) -> BytesIO | None:
        """
        Download an image from the given URL and return it as an in-memory binary stream.

        Args:
            url (str): URL of the image to download.

        Returns:
            BytesIO | None: A BytesIO containing image bytes on success. None otherwise.
        """

        try:
            response = requests.get(url, timeout=3000)
            response.raise_for_status()
            image = BytesIO(response.content)
            return image
        except Exception as e:
            logging.warning(f"Failed to process {url}: {e}")
            return None

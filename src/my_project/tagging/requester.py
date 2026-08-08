import logging
from io import BytesIO

import requests
from pydantic import ValidationError

from my_project.classes.helper_classes import (
    APIIssueResults,
    APISearchResults,
    ComicVineDetailStruct,
    ComicVineIssueStruct,
    Publisher,
)

logger = logging.getLogger(__name__)

header = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AutoComicLibrary/1.0 (contact: adam.perrott@protonmail.com;"
        "github.com/CloakedLeader/comic_library)"
    ),
    "Referer": "https://comicvine.gamespot.com/",
    "Accept": r"*/*",
    # "Accept-Encoding": "gzip,deflate,br",
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
        self.payload["format"] = "json"
        self.payload["limit"] = 50
        self.payload["resources"] = "volume"
        self.payload["field_list"] = (
            "id,image,publisher,name,start_year,date_added,"
            "count_of_issues,description,last_issue"
        )

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
        logger.info(f"The search URL is: {self.url_search}")

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
            headers=header,
        )
        prepared = req.prepare()
        self.url_iss = prepared.url
        logger.info(f"The issue URL is: {self.url_iss}")

    def search_get_request(self) -> APISearchResults:
        """
        Execute  a prepared GET request against the ComicVine API and return
        the parsed JSON.

        Raises:
            RuntimeError: If the required URL has not been build for the instance
                or there is an error on the server side.
            ValueError: If the required URL attribute exists but its value is None.

        Returns:
            APISearchResults: Parsed BaseModel Class when the API 'error' field is
                "OK". None if the API reports an error or invalid request syntax.
        """
        if not hasattr(self, "url_search"):
            raise RuntimeError("You must build url before sending request.")
        if self.url_search is None:
            raise ValueError("Search url cannot be None")
        response = self.session.get(self.url_search)
        if response.status_code != 200:
            logger.warning(
                f"Search request failed with status code: \
                    {response.status_code}"
            )
            logger.warning("\n" + response.text)
        data = response.json()
        if data["error"] != "OK":
            logger.warning("Error, please investigate")
            # raise RuntimeError("Error, please investigate")
        return APISearchResults.model_validate(data)

    def issue_get_request(self) -> APIIssueResults:
        """
        Execute  a prepared GET request against the ComicVine API and return
        the parsed JSON.

        Raises:
            RuntimeError: If the required URL has not been build for the instance
                or there is an error on the server side.
            ValueError: If the required URL attribute exists but its value is None.

        Returns:
            APISearchResults: Parsed BaseModel Class when the API 'error' field is
                "OK". None if the API reports an error or invalid request syntax.
        """
        if not hasattr(self, "url_iss"):
            raise RuntimeError("You must build url before sending request.")
        if self.url_iss is None:
            raise ValueError("issue url cannot be None")
        response = self.session.get(self.url_iss)
        if response.status_code != 200:
            logger.warning(
                f"Issue request failed with status code: \
                    {response.status_code}"
            )
            logger.warning("\n" + response.text)
        data = response.json()
        if data["error"] != "OK":
            logger.warning("Error, please investigate")
            # raise RuntimeError("Error, please investigate")
        items = data["results"]
        validated: list[ComicVineIssueStruct] = []
        for item in items:
            try:
                model_info = ComicVineIssueStruct.model_validate(item)
                validated.append(model_info)
            except ValidationError:
                continue
        data["results"] = validated
        return APIIssueResults.model_validate(data)

    def detail_get_request(self, volume_id: int) -> ComicVineDetailStruct:
        req = requests.Request(
            method="GET",
            url=f"{HttpRequest.base_address}/issue/4000-{volume_id}/",
            params={
                "api_key": self.api_key,
                "format": "json",
            },
            headers=header,
        )
        prepared = req.prepare()
        detail_url = prepared.url
        logger.info(f"The detail URL is: {detail_url}")

        if detail_url is None:
            raise ValueError("Detail url cannot be None")
        response = self.session.get(detail_url)
        if response.status_code != 200:
            logger.warning(
                f"Detail request failed with status code: \
                    {response.status_code}"
            )
            logger.warning("\n" + response.text)
        data = response.json()
        if data["error"] != "OK":
            logger.warning("Error, please investigate")
            # raise RuntimeError("Error, please investigate")
        items = data["results"]
        if data["number_of_page_results"] != 1:
            raise RuntimeError("Error, please investigate")

        return ComicVineDetailStruct.model_validate(items)

    def get_publisher_info(self, volume_id: int) -> Publisher:
        req = requests.Request(
            method="GET",
            url=f"{HttpRequest.base_address}/search/",
            params={
                "api_key": self.api_key,
                "format": "json",
                "filter": f"volume:{id}",
            },
            headers=header,
        )
        prepared = req.prepare()
        pub_url = prepared.url

        if pub_url is None:
            raise ValueError("Publisher url cannot be None")
        response = self.session.get(pub_url)
        if response.status_code != 200:
            logger.warning(
                f"Detail request failed with status code: \
                    {response.status_code}"
            )
            logger.warning("\n" + response.text)
        data = response.json()
        if data["error"] != "OK":
            logger.warning("Error, please investigate")
            # raise RuntimeError("Error, please investigate")
        items = data["results"]
        if len(items) != 1:
            raise RuntimeError("Error, please investigate")

        return Publisher.model_validate(data["publisher"])

    def download_img(self, url: str) -> BytesIO:
        """
        Download an image from the given URL and return it as an in-memory binary stream.

        Args:
            url (str): URL of the image to download.

        Returns:
            BytesIO | None: A BytesIO containing image bytes on success. None otherwise.
        """

        try:
            response = requests.get(url, timeout=3000, headers=header)
            response.raise_for_status()
            image = BytesIO(response.content)
            return image
        except Exception as e:
            logger.warning(f"Failed to process {url}: {e}")
            raise Exception from e

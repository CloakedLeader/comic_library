import os
import re
from typing import Optional

import aiofiles
import aiohttp
import requests
from bs4 import BeautifulSoup

from helper_classes import RSSComicInfo


class DownloadControllerAsync:
    """
    Asynchronous controller for handling comic download operations.

    This class coordinates between the view and download service to handle
    user interactions for downloading comics from RSS feeds. It manages the
    download workflow including status updates and error handling.
    """

    def __init__(self, view, service: "DownloadServiceAsync") -> None:
        """
        Initialise the download controller.

        Args:
            view: The view object for updating UI status.
            service: The download servie for handling actual file downloads.
        """
        self.view = view
        self.download_service = service
        self.comic_dict: dict[str, str] = {}

    async def handle_rss_comic_clicked(self, comic_info: RSSComicInfo) -> None:
        """
        Handle the event when an RSS comic is clicked for download.

        Args:
            comic_dict: Dictionary containing comic information with keys:
                - 'title': Comic title for display
                - 'link': URL to comic article page.
                - 'cover': URl to comic cover image.
                - 'pub_date': Publication date.
                - 'summary': Comic summary/description.

        This method orchestrates the download process by:
        1. Updating the view with the download status.
        2. Extracting the download links from the comic article page.
        3. Initiating the actual file download.
        4. Providing the user feedback on success or failure.

        Raises:
            requests.RequestException: If there are network issues accessing the page.
            aiohttp.ClientError: If there are issues with the async HTTP client.
            IOError: If there are file system issues during download.
        """
        self.comic_info = comic_info
        self.view.update_status(f"Starting download of: {comic_info.title}")
        try:
            download_link = self.download_service.get_download_links(comic_info.url)
            filepath = await self.download_service.download_comic(download_link)
            self.view.update_status(
                f"Successfully downloaded: {comic_info.title} to {filepath}"
            )
        except (requests.RequestException, aiohttp.ClientError, IOError) as e:
            self.view.update_status(f"Failed: {e}")


class DownloadServiceAsync:
    """
    Asynchronous service for downloading comic files.

    This class handles the actual downloading of the comic files, including
    link extraction from web pages, filename resolution and file management.
    It provides robust error handling and supports various comic file formats.
    """

    def __init__(
        self, download_folder: str = "D://adams-comics//0 - Downloads"
    ) -> None:
        """
        Initialise the download service.

        Args:
            download_folder: Path to the folder where comics will be downloaded.

        The download folder will be created if it does not exist.
        """
        self.download_folder = download_folder
        os.makedirs(download_folder, exist_ok=True)

    def get_filename_from_header(self, content_disposition: str) -> Optional[str]:
        """
        Extract filename from Content-Disposition header.

        Args:
            content_disposition: The Content-Disposition header value
        from HTTP response.

        Returns:
            The extracted filename, or None if not found or invalid.

        Uses regex pattern matching to find filename in the header, handling both
        quoted and unquoted filename values.

        """
        if content_disposition:
            fname = re.findall('filename="?([^"]+)"?', content_disposition)
            if fname:
                return fname[0]
            else:
                return None
        else:
            return None

    def get_download_links(self, comic_article_link: str) -> str:
        """
        Extract download links from a comic article page.

        Args:
            comic_article_link: URL of the comic article page to scrape.

        Returns:
            The first download link found on the page.

        Raises:
            ValueError: If no download links are found on the page.
            requests.RequestException: If there are issues accessing the webpage.

        Scrapes the article page looking for div elements with class "aio-button-center"
        and extracts download links from anchor tags within them. Prints all found links
        for debugging.
        """
        headers = {"User-Agent": "Mozilla/5.0"}

        response = requests.get(comic_article_link, headers, timeout=30)
        soup = BeautifulSoup(response.content, "html.parser")

        download_links = []

        for button_div in soup.find_all("div", class_="aio-button-center"):
            link = button_div.find("a", href=True)
            if link:
                href = link["href"]
                title = link.get("title", "").strip()
                download_links.append((title, href))

        if not download_links:
            raise ValueError("No download links found on the page")
        return download_links[0][1]

    async def download_comic(self, comic_download_link: str) -> str:
        """
        Download comic file asynchronously.

        Args:
            comic_download_link: URL of the comic file download.

        Returns:
            The full path of the downloaded file.

        Raises:
            Exception: If the download fails or HTTP status is not 200.
            IOError: If there issues writing the file to disk.

        Downloads the file in chunks to handle large files efficiently.
        Attempts to get filename from Content-Disposition header, falls back
        to URL path, finally, uses "downloaded_comic.cbz" as a last resort.
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(comic_download_link) as response:
                if response.status != 200:
                    raise Exception(
                        f"Download failed with status code {response.status}"
                    )

                filename = self.get_filename_from_header(
                    response.headers.get("content-disposition")
                )

                if not filename:
                    filename = "downloaded_comic.cbz"

                filepath = os.path.join(self.download_folder, filename)

                async with aiofiles.open(filepath, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
                return filepath

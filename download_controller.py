import logging
import os
import re
import urllib.parse
from email.header import decode_header
from pathlib import Path
from typing import Callable, Optional

import aiofiles
import aiohttp
import requests
from bs4 import BeautifulSoup

from classes.helper_classes import RSSComicInfo

logging.getLogger("aiofiles").setLevel(logging.WARNING)


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
        print(f"[DEBUG] comic_info.title type: {type(comic_info.title)}")
        print(f"[DEBUG] comic_info.url: {comic_info.url}")
        download_links = self.download_service.get_download_links(comic_info.url)
        download_links = self.download_service.sort(download_links)
        download_now_link = download_links[0][1]
        try:
            filepath = await self.download_service.download_comic(
                download_now_link, self.progress_update
            )
        except (requests.RequestException, aiohttp.ClientError, IOError) as e:
            print(e)
            return
        for service, link in download_links:
            if service != "Read Online":
                try:
                    filepath = await self.download_service.download_from_service(
                        service,
                        link,
                        progress_callback=self.progress_update,
                    )
                except (requests.RequestException, aiohttp.ClientError, IOError) as e:
                    print(e)
                    continue
                self.view.update_status(
                    f"Successfully downloaded: {comic_info.title} to {filepath}"
                    + " via service: "
                    + str(service)
                )
                break

    def progress_update(self, percent: int):
        self.view.update_progress_bar(percent)


class DownloadServiceAsync:
    """
    Asynchronous service for downloading comic files.

    This class handles the actual downloading of the comic files, including
    link extraction from web pages, filename resolution and file management.
    It provides robust error handling and supports various comic file formats.
    """

    def __init__(self, download_folder: str = "D:/adams-comics/0 - Downloads") -> None:
        """
        Initialise the download service.

        Args:
            download_folder: Path to the folder where comics will be downloaded.

        The download folder will be created if it does not exist.
        """
        self.download_folder = download_folder
        os.makedirs(download_folder, exist_ok=True)

    def get_filename(self, content_disposition: str) -> Optional[str]:
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
        if not content_disposition:
            return None

        filename_star = re.search(
            r"filename\*\s*=\s*UTF-8\'\'(.+)", content_disposition, flags=re.IGNORECASE
        )
        if filename_star:
            return urllib.parse.unquote(filename_star.group(1))

        match = re.search(
            r'filename\s*=\s*"?(=\?.+\?=)"?', content_disposition, flags=re.IGNORECASE
        )
        if match:
            decoded_parts = decode_header(match.group(1))
            return "".join(
                part.decode(encoding or "utf-8") if isinstance(part, bytes) else part
                for part, encoding in decoded_parts
            )

        filename = re.search(
            r'filename\s*=\s*"?(?P<name>[^";]+)"?', content_disposition, re.IGNORECASE
        )
        return filename.group("name") if filename else None

    def get_download_links(self, comic_article_link: str) -> list[tuple[str, str]]:
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
        # TODO: Scrape comic title from website for fallback naming.
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
        return download_links

    async def download_comic(
        self, comic_download_link: str, progress_callback: Callable
    ) -> str:
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
        headers = {"User-Agent": "Mozilla/5.0"}

        async with aiohttp.ClientSession(headers=headers) as session:

            async with session.get(
                comic_download_link, allow_redirects=True
            ) as response:
                print("\n=== Redirect history ===")
                for i, r in enumerate(response.history, start=1):
                    print(f"\nHop {i}: {r.url}")
                    print(r.headers)

                print("\n=== Final response ===")
                print(response.url.human_repr())
                print(dict(response.headers))

                if response.status != 200:
                    raise Exception(
                        f"Download failed with status code {response.status}"
                    )

                max_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0

                filename = None

                for r in response.history:
                    loc = r.headers.get("Location")
                    if loc:
                        parsed_loc = urllib.parse.urlparse(loc)
                        last_segment = os.path.basename(parsed_loc.path)
                        if last_segment:
                            filename = urllib.parse.unquote(last_segment)
                            break

                if not filename:
                    last_segment = os.path.basename(response.url.path)
                    if last_segment:
                        filename = urllib.parse.unquote(last_segment)

                if not filename:
                    print("Could not determine filename from redirects or final URL")
                    filename = "downloaded_comic.cbz"

                if not os.path.splitext(filename)[1]:
                    filename += ".cbz"
                filepath = os.path.join(self.download_folder, filename)

                async with aiofiles.open(filepath, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
                        downloaded += len(chunk)

                        print(f"[DEBUG] Writing {len(chunk)} bytes to file...")
                        percent = int(downloaded * 100 / max_size)
                        progress_callback(percent)

                return filepath

    async def pixeldrain_download(
        self, download_link: str, progress_callback: Callable
    ) -> str:
        file_id = self.follow_pixeldrain_redirect(download_link)
        download_path = Path(self.download_folder)
        base_link = "https://pixeldrain.com/api/file/"

        meta_suffix = f"{file_id}/info"
        meta_url = base_link + meta_suffix
        async with aiohttp.ClientSession() as session:
            async with session.get(meta_url) as meta_response:
                meta_data = await meta_response.json()

            filename = meta_data["name"]
            file_size = meta_data["size"]
            downloaded = 0
            filepath = download_path / filename

            download_suffix = f"{file_id}?download"
            download_url = base_link + download_suffix

            async with session.get(download_url) as response:
                async with aiofiles.open(filepath, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
                        downloaded += len(chunk)
                        print(f"[DEBUG] Writing {len(chunk)} bytes to file...")
                        percent = int(downloaded * 100 / file_size)
                        progress_callback(percent)

        print(f"Downloaded: {filename}")
        return str(filepath)

    async def download_from_service(self, service: str, link: str, progress_callback):
        DOWNLOAD_HANDLERS = {
            "DOWNLOAD NOW": self.download_comic,
            "PIXELDRAIN": self.pixeldrain_download,
        }
        handler = DOWNLOAD_HANDLERS.get(service)
        if handler:
            filepath = await handler(link, progress_callback)
            return filepath
        else:
            print(f"No handler for service: {service}")
            return None

    @staticmethod
    def follow_pixeldrain_redirect(link: str) -> str:
        response = requests.get(link, allow_redirects=True, timeout=3000)
        final_url = response.url
        return final_url.split("/")[-1]

    @staticmethod
    def sort(links: list[tuple]) -> list[tuple]:
        service_priority = ["DOWNLOAD NOW", "PIXELDRAIN", "TERABOX", "MEGA"]
        return sorted(
            links,
            key=lambda pair: (
                service_priority.index(pair[0])
                if pair[0] in service_priority
                else len(service_priority)
            ),  # # noqa: E501
        )

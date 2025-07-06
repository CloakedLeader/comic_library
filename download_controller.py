import os
import re
from typing import Optional
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

import aiohttp
import aiofiles

class DownloadControllerAsync:
    """Asynchronous controller for handling comic download operations.
    
    This class coordinates between the view and download service to handle
    user interactions for downloading comics from RSS feeds. It manages
    the download workflow including status updates and error handling.
    """
    def __init__(self, view, service) -> None:
        """Initialize the download controller.
        
        Args:
            view: The view object for updating UI status messages
            service: The download service for handling actual file downloads
        """
        self.view = view
        self.download_service = service
        self.comic_dict = None
    
    async def handle_rss_comic_clicked(self, comic_dict) -> None:
        """Handle the event when an RSS comic is clicked for download.
        
        Args:
            comic_dict: Dictionary containing comic information with keys:
                       - 'title': Comic title for display
                       - 'link': URL to the comic article page
                       - 'cover': Cover image URL
                       - 'pub_date': Publication date
                       - 'summary': Comic summary
            
        This method orchestrates the download process by:
        1. Updating the view with download status
        2. Extracting download links from the comic article page
        3. Initiating the actual file download
        4. Providing user feedback on success or failure
        
        Raises:
            requests.RequestException: If there are network issues accessing the page
            aiohttp.ClientError: If there are issues with the async HTTP client
            IOError: If there are file system issues during download
        """
        self.comic_dict = comic_dict
        self.view.update_status(f"Starting download of: {comic_dict['title']}")
        try:
            download_link = self.download_service.get_download_links(comic_dict.get("link"))
            filepath = await self.download_service.download_comic(download_link)
            self.view.update_status(f"Successfully downloaded: {comic_dict.get('title')} to {filepath}")
        except (requests.RequestException, aiohttp.ClientError, IOError) as e:
            self.view.update_status(f"Failed: {e}")
 
class DownloadServiceAsync:
    """Asynchronous service for downloading comic files.
    
    This class handles the actual downloading of comic files, including
    link extraction from web pages, filename resolution, and file management.
    It provides robust error handling and supports various comic file formats.
    """
    def __init__(self, download_folder="D://Comics//To Be Sorted"):
        """Initialize the download service.
        
        Args:
            download_folder: Path to the folder where comics will be downloaded.
                           Defaults to "D://Comics//To Be Sorted"
                           
        The download folder will be created if it does not exist.
        """
        self.download_folder = download_folder
        os.makedirs(download_folder, exist_ok=True)

    def get_filename_from_header(self, content_disposition: Optional[str]) -> Optional[str]:
        """Extract filename from Content-Disposition header.
        
        Args:
            content_disposition: The Content-Disposition header value from HTTP response
            
        Returns:
            Optional[str]: The extracted filename, or None if not found or invalid
            
        Uses regex pattern matching to find filename in the header, handling both
        quoted and unquoted filename values.
        """
        if not content_disposition:
            return None
        fname = re.findall('filename="?([^"]+)"?', content_disposition)
        if len(fname) == 0:
            return None
        return fname[0]

    def get_download_links(self, comic_article_link: str) -> str:
        """Extract download links from a comic article page.
        
        Args:
            comic_article_link: URL of the comic article page to scrape
            
        Returns:
            str: The first download link found on the page
            
        Raises:
            ValueError: If no download links are found on the page
            requests.RequestException: If there are issues accessing the web page
            
        Scrapes the article page looking for div elements with class "aio-button-center"
        and extracts download links from anchor tags within them. Prints all found
        links for debugging purposes.
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

        for title, link in download_links:
            print(f"{title}: {link}")
        if not download_links:
            raise ValueError("No download links found on the page")
        return download_links[0][1]

    async def download_comic(self, comic_download_link: str) -> str:
        """Download a comic file asynchronously.
        
        Args:
            comic_download_link: URL of the comic file to download
            
        Returns:
            str: The full path to the downloaded file
            
        Raises:
            Exception: If the download fails or HTTP status is not 200
            IOError: If there are issues writing the file to disk
            
        Downloads the file in chunks to handle large files efficiently.
        Attempts to get filename from Content-Disposition header, falls back
        to URL path, and uses "downloaded_comic.cbz" as last resort.
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(comic_download_link) as response:
                if response.status_code != 200:
                    raise Exception(f"Download failed with status code {response.status}")

                filename = await self.get_filename_from_header(response.headers.get('content-disposition'))
                if not filename:
                    filename = os.path.basename(urlparse(comic_download_link).path)
                if not filename:
                    filename = "downloaded_comic.cbz"

                filepath = os.path.join(self.download_folder, filename)

                async with aiofiles.open(filepath, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
                return filepath

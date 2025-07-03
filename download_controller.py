import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re
import asyncio
import aiohttp


class DownloadControllerAsync:
    def __init__(self, view, service):
        self.view = view
        self.download_service = service
    
    async def handle_rss_comic_clicked(self, comic_dict):
        self.comic_dict = comic_dict
        self.view.update_status(f"Starting download of: {comic_dict['title']}")
        try:
            download_link = self.download_service.get_download_links(comic_dict.get("link"))
            filepath = self.download_service.download_comic(download_link)
            self.view.update_status(f"Successfull downloaded: {comic_dict.get('title')}")
        except Exception as e:
            self.view.update_status(f"Failed: {e}") 
 
class DownloadServiceAsync:
    def __init__(self, download_folder="D://Comics//To Be Sorted"):
        self.download_folder = download_folder
        os.makedirs(download_folder, exist_ok=True)

    async def get_filename_from_header(self, content_disposition):
        if not content_disposition:
            return None
        fname = re.findall('filename="?([^"]+)"?', content_disposition)
        if len(fname) == 0:
            return None
        return fname[0]

    def get_download_links(self, comic_article_link: str) -> str:
        headers = {"User-Agent": "Mozzilla/5.0"}

        response = requests.get(comic_article_link, headers)
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

        return download_links[0][1]

    async def download_comic(self, comic_download_link: str) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(comic_download_link) as response:

                response = requests.get(comic_download_link, stream=True)
                if response.status_code != 200:
                    raise Exception(f"Download failed with status code {response.status_code}")
        
                filename = self.get_filename_from_header(response.headers.get('content-disposition'))
                if not filename:
                    filename = os.path.basename(urlparse(comic_download_link).path)
                if not filename:
                    filename = "downloaded_comic.cbz"
        
                filepath = os.path.join(self.download_folder, filename)
            
                with open(filepath, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return filepath

        
        
        
        




from download_controller import DownloadServiceAsync
from pathlib import Path
import requests
from bs4 import BeautifulSoup

def dummy(num):
    print(num)

service = DownloadServiceAsync(Path("0 - Downloads"))
response = requests.get("https://getcomics.org/marvel/werewolf-by-night-red-band-7-2025/", timeout=30)
soup = BeautifulSoup(response.content, "html.parser")
print(soup)


# article_link = service.get_download_links("https://getcomics.org/marvel/werewolf-by-night-red-band-7-2025/")


# simple_link = download_link[0]
# print(simple_link)
# filepath = service.download_comic(download_link, dummy)

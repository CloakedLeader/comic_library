from download_controller import DownloadServiceAsync
from pathlib import Path
import asyncio

def dummy(num):
    pass

async def main():
    async with DownloadServiceAsync(Path("0 - Downloads")) as downloader:
        download_links = await downloader.get_download_links(r"https://getcomics.org/marvel/werewolf-by-night-red-band-7-2025/")
    
        simple_link = download_links[0][1]
        print(simple_link)
        filepath = await downloader.download_comic(simple_link, dummy)

if __name__ == "__main__":
    asyncio.run(main())

import feedparser
import requests
from bs4 import BeautifulSoup

def rss_scrape() -> list[dict]:
    """
    Scrapes the rss feed of GetComics and returns a list of dictionaries with the following structure:
    {
    title: The title of the page on GetComics.
    link: The link of the article on GetComics.
    pub_date: The date the article was published on GetComics.
    summary: The description (or blurb) of the comic, filtered out of the html summary.
    cover_link: The link to the cover image for display purposes.
    }
    """
    base_url = "https://getcomics.org/feed/"
    feed = feedparser.parse(base_url)
    entries = []
    entries = [
        {"title": e.title, "link": e.link, "pub_date": e.get("published", None), "summary": e.summary}
        for e in feed.entries
    ]
    entries = [e for e in entries if is_comic_entry(e)]
    for entry in entries:
        total_summary = entry.get("summary")
        comic_description = summary_scrape(total_summary)
        entry["summary"] = comic_description
        res = requests.get(entry.get("link"), headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        soup = BeautifulSoup(res.text, "html.parser")
        meta_tag = soup.find("meta", property="og:image")
        image_url = meta_tag.get("content") if meta_tag else None
        entry["cover_link"] = image_url if image_url else None
      
    return entries


def is_metadata_paragraph(paragraph) -> bool:
    text = paragraph.get_text(strip=True).lower()
    return text.startswith(("year", "size")) or ("year" in text and "size" in text)

  
def summary_scrape(html_formatted_string) -> str:
    soup = BeautifulSoup(html_formatted_string, "html.parser")
    paragraphs = soup.find_all("p")
    description_paragraphs = []
    for i, p in enumerate(paragraphs):
        text = p.get_text(strip=True)

        if not text:
            continue
        lower_text = text.lower()

        if i == 0 and "getcomics" in lower_text:
            continue
        if i == len(paragraphs) - 1 and (
            "the post" in lower_text or "appeared first on" in lower_text
        ):
            continue

        if is_metadata_paragraph(p):
            continue
        
        description_paragraphs.append(text)

    return "\n\n".join(description_paragraphs)

def is_comic_entry(entry):
    link_blacklist = ["/news/", "/announcement/", "/blog"]
    title_blacklist = ["weekly pack"]
    link_lower = entry["link"].lower()
    title_lower = entry["title"].lower()

    return not (any(keyword in link_lower for keyword in link_blacklist) or
                any(keyword in title_lower for keyword in title_blacklist))

def download_comic(comic_info: dict) -> list[tuple[str, str]]:
    url = comic_info.get("link")
    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(url, headers, timeout=30)
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

    return download_links

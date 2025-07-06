import feedparser
import requests
from bs4 import BeautifulSoup

def rss_scrape() -> list[dict]:
    """Scrape and process RSS feed data from GetComics website.
    
    Fetches the RSS feed, filters comic entries, and extracts relevant
    information including title, link, publication date, summary, and cover image.
    
    Returns:
        list[dict]: A list of dictionaries containing comic information
        
    Each dictionary contains:
        - title: Comic title
        - link: Article link  
        - pub_date: Publication date
        - summary: Cleaned summary text
        - cover_link: Cover image URL
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
    """Check if a paragraph contains metadata keywords.
    
    Args:
        paragraph: BeautifulSoup paragraph element to check
        
    """Clean and extract summary text from HTML formatted string.
    
    Removes metadata paragraphs and promotional content to extract
    the core summary information.
    
    Args:
        html_formatted_string: HTML formatted summary string
        
    Returns:
        str: Cleaned summary text with metadata and promotional content removed
    """
    Returns:
        bool: True if the paragraph contains metadata keywords like 'year' or 'size'
    """
        image_url = meta_tag.get("content") if meta_tag else None
        entry["cover_link"] = image_url if image_url else None
    return entries

def is_metadata_paragraph(paragraph: BeautifulSoup) -> bool:
    text = paragraph.get_text(strip=True).lower()
    return text.startswith(("year", "size")) or ("year" in text and "size" in text)

  
def summary_scrape(html_formatted_string: str) -> str:
    soup = BeautifulSoup(html_formatted_string, "html.parser")
    """Filter comic entries based on blacklists applied to links and titles.
    
    Args:
        entry: Dictionary containing entry information with 'link' and 'title' keys
        
    Returns:
        bool: True if the entry is a valid comic entry (not blacklisted)
    """
    paragraphs = soup.find_all("p")
    """Extract download links from a comic page.
    
    Fetches the comic page, parses HTML to find download buttons,
    and extracts download links with their titles.
    
    Args:
        comic_info: Dictionary containing comic information with 'link' key
        
    Returns:
        list[tuple[str, str]]: List of tuples containing (title, download_url)
        
    The function looks for div elements with class "aio-button-center"
    and extracts download links from anchor tags within them.
    """
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

def is_comic_entry(entry: dict[str, str]) -> bool:
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

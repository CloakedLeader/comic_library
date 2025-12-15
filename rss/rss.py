from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser  # type: ignore[import-untyped]
import requests
from bs4 import BeautifulSoup


def rss_scrape(latest_link: str | None) -> list[dict]:
    """
    Scrapes and processes RSS feed data from GetComics website.

    Fetches the RSS feed, filters comic entries and extracts relevant information
    including title, link, date and a link to the cover image.

    Raises:
        ValueError: If the comic entry in the RSS feed has no link attribute.

    Returns:
        list[dict]: A list of dictionaries containing the required information.
            Each dictionary contains:
                - title
                - link
                - pub_date
                - summary
                - cover_link

    """
    base_url = "https://getcomics.org/feed/"
    feed = feedparser.parse(base_url)
    new_entries = []
    for e in feed.entries:
        link = e.get("link")
        if link is None:
            continue
        if latest_link is not None and link == latest_link:
            break
        entry = {
            "title": e.title,
            "link": link,
            "pub_date": e.get("published", None),
            "summary": e.summary,
        }
        if not is_comic_entry(entry):
            continue
        new_entries.append(entry)

    new_entries.reverse()

    return format_rss(new_entries)


def format_rss(list_of_entries: list[dict]) -> list[dict]:
    for entry in list_of_entries:
        total_summary = entry.get("summary", "")
        comic_description = summary_scrape(total_summary)
        entry["summary"] = comic_description
        raw = entry["pub_date"]
        entry["pub_date"] = parse_pub_date(raw)
        link = entry.get("link")
        if link is None:
            raise ValueError("link cannot be None")
        res = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        soup = BeautifulSoup(res.text, "html.parser")
        meta_tag = soup.find("meta", property="og:image")
        image_url = meta_tag.get("content") if meta_tag else None
        entry["cover_link"] = image_url if image_url else None
    return list_of_entries


def is_metadata_paragraph(paragraph: BeautifulSoup) -> bool:
    """
    Checks if a paragraph in a html style string contains metadata keywords.

    Args:
        paragraph (BeautifulSoup): A BeautifulSoup paragraph element to check.

    Returns:
        bool: True if the paragraph contains metadata keywords, else False.
    """

    text = paragraph.get_text(strip=True).lower()
    return text.startswith(("year", "size")) or ("year" in text and "size" in text)


def summary_scrape(html_formatted_string: str) -> str:
    """
    Removes metadata paragraphs and promotional content to extract
    the core summary information.

    Args:
        html_formatted_string (str): A HTML formatted string extracted
    from the RSS feed.

    Returns:
        str: Cleaned summary text, basically just the description of the comic.
    """

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


def is_comic_entry(entry: dict[str, str]) -> bool:
    """
    Filters comic entries based on blacklists applied to links
    and titles.

    Args:
        entry(dict[str, str]): Dictionary containing information scraped from
    the RSS feed.

    Returns:
        bool: True if the entry is a valid comic entry. Otherwise False.
    """

    link_blacklist = ["/news/", "/announcement/", "/blog"]
    title_blacklist = ["weekly pack"]
    link_lower = entry["link"].lower()
    title_lower = entry["title"].lower()

    return not (
        any(keyword in link_lower for keyword in link_blacklist)
        or any(keyword in title_lower for keyword in title_blacklist)
    )


def parse_pub_date(pub_date_str: str) -> int:
    """
    Translates the date from the format in the RSS feed to UNIX time for easy comparisons
    in the database.

    Args:
        pub_date_str (str): The date that the RSS feed has for the comic being uploaded.

    Returns:
        int: The UNIX time representation of the time.
    """

    try:
        dt = parsedate_to_datetime(pub_date_str)
    except Exception:
        dt = datetime.strptime(pub_date_str, "%Y-%m-%d %H:%M:%S")
    return int(dt.timestamp())

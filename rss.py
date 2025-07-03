import feedparser
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def rss_scrape():
    base_url = "https://getcomics.org/feed/"
    feed = feedparser.parse(base_url)
    entries = []
    entries = [{"title": e.title, "link": e.link, "pub_date": e.get("published", None), "summary": e.summary} for e in feed.entries]
    entries = [e for e in entries if is_comic_entry(e)]
    for entry in entries:
        total_summary = entry.get("summary")
        comic_description = summary_scrape(total_summary)
        entry["summary"] = comic_description
        res = requests.get(entry.get("link"), headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        meta_tag = soup.find("meta", property="og:image")
        image_url = meta_tag.get("content") if meta_tag else None
        if image_url:
            entry["cover_link"] = image_url
        
    return entries

def get_rss_cover_img_url(entries: list):
    for i in entries:
        res = requests.get(i["link"], headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        meta_tag = soup.find("meta", property="og:image")
        image_url = meta_tag.get("content") if meta_tag else None
        if image_url:
            i["cover_link"] = image_url
        else:
            continue

def is_metadata_paragraph(paragraph):
    text = paragraph.get_text(strip=True).lower()
    if text.startswith("year") or text.startswith("size"):
        return True
    if "year" in text and "size" in text:
        return True
    return False

  
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
        if i == len(paragraphs) - 1 and ("the post" in lower_text or "appeared first on" in lower_text):
            continue

        if is_metadata_paragraph(p):
            continue
        
        description_paragraphs.append(text)

    return "\n\n".join(description_paragraphs)

def download_comic(comic_info: dict) -> None:
    url = comic_info.get("link")
    headers = {"User-Agent": "Mozzilla/5.0"}

    reponse = requests.get(url, headers)
    soup = BeautifulSoup(reponse.content, "html.parser")

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

def download_third_party_links(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)

        page.wait_for_selector("a:has-text('Download'), button:has-text('Download')", timeout=30000)
        page.click("a:has-text('Download'), button:has-text('Download')")

        page.wait_for_timeout(3000)

        final_url = page.url
        browser.close()
        return final_url
    
def is_comic_entry(entry):
    link_blacklist = ["/news/", "/announcement/", "/blog"]
    title_blacklist = ["weekly pack"]
    link_lower = entry["link"].lower()
    title_lower = entry["title"].lower()

    if any(keyword in link_lower for keyword in link_blacklist):
        return False
    if any(keyword in title_lower for keyword in title_blacklist):
        return False
    return True

rss_scrape()
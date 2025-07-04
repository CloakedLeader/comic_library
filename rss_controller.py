import sqlite3
from datetime import datetime, timedelta
import feedparser
import requests
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
from rss import rss_scrape


class RSSController:
    def __init__(self, repository):
        self.repo = repository
        self.rss_results = rss_scrape()

    def add_rss_to_db(self):
        self.repo.delete_old_entries()
        if self.is_new_update():
            self.repo.insert_entries(self.rss_results)
        
    def is_new_update(self) -> bool:
        latest_db_date = self.repo.get_latest_pub_date()
        if not latest_db_date:
            return True
        latest_db_date = parsedate_to_datetime(latest_db_date)

        latest_feed_date = parsedate_to_datetime(self.rss_results[0]["pub_date"])

        return latest_feed_date > latest_db_date
    
    def get_recent_comic_info(self, number_of_entries):
        entries = self.repo.get_recent_entries(limit=number_of_entries)
        output = []
        for title, cover_url in entries:
            output.append({"title": title, "cover_link": cover_url})
        self.close()
        return output
    
    def run(self, num):
        self.repo.delete_old_entries()
        if self.is_new_update():
            self.add_rss_to_db()
        return self.get_recent_comic_info(num)

    def close(self):
        self.repo.close()
    
    

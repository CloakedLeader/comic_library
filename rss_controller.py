from email.utils import parsedate_to_datetime
from rss import rss_scrape

from rss_repository import RSSRepository
class RSSController:
    def __init__(self, repository: RSSRepository) -> None:
        self.repo = repository
        self.rss_results = rss_scrape()

    def add_rss_to_db(self) -> None:
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
    
    def get_recent_comic_info(self, number_of_entries: int) -> list[dict[str, str]]:
        entries = self.repo.get_recent_entries(limit=number_of_entries)
        output = []
        for title, cover_url in entries:
            output.append({"title": title, "cover_link": cover_url})
        return output
    
    def run(self, num: int) -> list[dict[str, str]]:
        self.add_rss_to_db()
        result = self.get_recent_comic_info(num)
        self.close()
        return result

    def close(self) -> None:
        self.repo.close()

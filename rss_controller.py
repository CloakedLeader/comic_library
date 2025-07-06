from email.utils import parsedate_to_datetime
from rss import rss_scrape

from rss_repository import RSSRepository
    """Controller for managing RSS feed data integration with repository.
    
    This class handles fetching RSS feed data, updating the database,
    and retrieving recent comic information with date-based update checks.
    """
        """Initialize the RSS controller.
        
        Args:
            repository: RSSRepository instance for database operations
        """
class RSSController:
    def __init__(self, repository: RSSRepository) -> None:
        self.repo = repository
        """Update the database with new RSS entries.
        
        Deletes old entries and inserts new ones from the RSS feed
        if there are newer entries than the latest stored entry.
        """
        self.rss_results = rss_scrape()

    def add_rss_to_db(self) -> None:
        self.repo.delete_old_entries()
        if self.is_new_update():
        """Check if the RSS feed contains newer updates than stored data.
        
        Compares the publication date of the latest RSS entry with the
        latest entry in the database using email date parsing.
        
        Returns:
            bool: True if there are newer updates available, False otherwise
        """
            self.repo.insert_entries(self.rss_results)
        
    def is_new_update(self) -> bool:
        latest_db_date = self.repo.get_latest_pub_date()
        if not latest_db_date:
            return True
        """Retrieve recent comic information from the database.
        
        Args:
            number_of_entries: Maximum number of entries to retrieve
            
        Returns:
            list[dict[str, str]]: List of dictionaries with 'title' and 'cover_link' keys
        """
        latest_db_date = parsedate_to_datetime(latest_db_date)

        latest_feed_date = parsedate_to_datetime(self.rss_results[0]["pub_date"])

        """Orchestrate the update and retrieval process.
        
        Ensures database freshness by checking for updates and adding new data
        if needed, then returns recent comic information and closes the repository.
        
        Args:
            num: Number of recent entries to return
            
        Returns:
            list[dict[str, str]]: List of recent comic information dictionaries
        """
        return latest_feed_date > latest_db_date
        """Close the repository connection.
        
        Commits any pending transactions and closes the database connection.
        """
    
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

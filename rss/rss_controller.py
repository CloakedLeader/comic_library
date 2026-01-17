from classes.helper_classes import RSSComicInfo
from rss.rss import rss_scrape
from rss.rss_repository import RSSRepository


class RSSController:
    """
    Controller for managing RSS feed data and integration with database.

    This class handles fetching RSS feed data, updating the database and
    retrieving recent comic information with date-based update checks.
    """

    def __init__(self, repository: RSSRepository) -> None:
        """
        Initialise the RSS controller.

        Args:
            repository: RSSRepository instance for database operations.
        """
        self.repo = repository
        self.rss_results = rss_scrape()

    def add_rss_to_db(self) -> None:
        """
        Updates the database with new RSS entries.

        Deletes old entries and inserts new ones from the RSS feed if there
        are newer entries than the latest stored one.
        """
        self.repo.delete_old_entries()
        self.repo.insert_entries(self.rss_results)

    def get_recent_comic_info(self, number_of_entries: int) -> list[RSSComicInfo]:
        """
        Retrieves recent comic information from the database.

        Args:
            number_of_entries: Maximum number of entries to retrieve.

        Returns:
            A list of dictionaries with 'title' and 'cover_link' keys.
        """
        entries = self.repo.get_recent_entries(limit=number_of_entries)
        output = []
        for url, title, cover_url in entries:
            output.append(RSSComicInfo(url=url, title=title, cover_url=cover_url or ""))
        return output

    def run(self, num: int) -> list[RSSComicInfo]:
        """
        Orchestrates the update and retrieval process.

        Ensures database freshness by checking for updates and adding
        new data if needed, then returns recent comic information and
        closes the repository.

        Args:
            num: The number of recent entries to return.

        Returns:
            A list of dictionaries of recent comic information.
        """
        self.add_rss_to_db()
        result = self.get_recent_comic_info(num)
        self.close()
        return result

    def close(self) -> None:
        """
        Close the repository connection.

        Commits any pending transactions and closes the database connection.
        """
        self.repo.close()

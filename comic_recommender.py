from typing import Optional

Comic = dict[str, any]


class ComicRecommender:
    def __init__(self, comics_db: List[Comic]) -> None:
        self.comics = comics_db

    def get_next_in_series(self, current: Comic) -> Optional[Comic]:
        same_series = [
            c for c in self.comics
            if c["series"] == current["series"]
        ]
        # TODO: Implement logic to find next comic based on issue number
        # FOr now return None until implementation is complete
        return None
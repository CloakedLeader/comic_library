from typing import List, Dict, Tuple, Optional

Comic = Dict[str, any]


class ComicRecommender:
    def __init__(self, comics_db: List[Comic]):
        self.comics = comics_db

    def get_next_in_series(self, current) -> Optional[Comic]:
        same_series = [
            c for c in self.comics
            if c["series"] == current["series"]
        ]
        pass
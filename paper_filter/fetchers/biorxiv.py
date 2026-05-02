"""bioRxiv API fetcher."""

from datetime import datetime, timedelta

import requests

from ..models import Paper
from .base import FeedFetcher


class BiorxivFetcher(FeedFetcher):
    """Fetch from bioRxiv API by date."""

    API_URL = "https://api.biorxiv.org/details/biorxiv"

    def fetch(self) -> list[Paper]:
        """Fetch all papers from the most recent day with submissions."""
        papers = []

        # Try yesterday first, then today if no results
        # (bioRxiv updates throughout the day)
        for days_ago in [1, 0, 2]:
            target_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            papers = self._fetch_date(target_date)
            if papers:
                print(f"  bioRxiv: fetching papers from {target_date}")
                break

        return papers

    def _fetch_date(self, date: str) -> list[Paper]:
        """Fetch all papers from a specific date (handles pagination)."""
        papers = []
        cursor = 0

        while True:
            try:
                url = f"{self.API_URL}/{date}/{date}/{cursor}"
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                data = response.json()

                collection = data.get("collection", [])
                if not collection:
                    break

                for item in collection:
                    paper = Paper(
                        title=item.get("title", "").replace("\n", " "),
                        authors=self._parse_authors(item.get("authors", "")),
                        abstract=item.get("abstract", ""),
                        url=f"https://www.biorxiv.org/content/{item.get('doi', '')}v{item.get('version', '1')}",
                        source="bioRxiv",
                        categories=[item.get("category", "")],
                        published=item.get("date", ""),
                    )
                    papers.append(paper)

                # Check if more pages (API returns 100 per page)
                if len(collection) < 100:
                    break
                cursor += 100

            except Exception as e:
                print(f"Error fetching bioRxiv: {e}")
                break

        return papers

    def _parse_authors(self, authors_str: str) -> list[str]:
        """Parse author string (semicolon or comma separated)."""
        if not authors_str:
            return []
        # bioRxiv API returns authors semicolon-separated
        if ";" in authors_str:
            return [a.strip() for a in authors_str.split(";") if a.strip()]
        return [a.strip() for a in authors_str.split(",") if a.strip()]

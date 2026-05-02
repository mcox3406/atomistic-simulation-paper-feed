"""ChemRxiv API fetcher."""

from datetime import datetime, timedelta

import requests

from ..models import Paper
from .base import FeedFetcher


class ChemrxivFetcher(FeedFetcher):
    """Fetch from ChemRxiv public API."""

    API_URL = "https://chemrxiv.org/engage/chemrxiv/public-api/v1/items"

    def fetch(self) -> list[Paper]:
        """Fetch all papers from the last 2 days (handles timezone issues)."""
        papers = []
        skip = 0
        limit = 50

        # Use 2-day window to handle timezone edge cases
        date_from = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        date_to = datetime.now().strftime("%Y-%m-%d")
        print(f"  ChemRxiv: fetching papers from {date_from} to {date_to}")

        while True:
            try:
                response = requests.get(
                    self.API_URL,
                    params={
                        "searchDateFrom": date_from,
                        "searchDateTo": date_to,
                        "limit": limit,
                        "skip": skip,
                    },
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()

                items = data.get("itemHits", [])
                if not items:
                    break

                for item in items:
                    item_data = item.get("item", item)

                    # Extract authors
                    authors = []
                    for author in item_data.get("authors", []):
                        name = f"{author.get('firstName', '')} {author.get('lastName', '')}".strip()
                        if name:
                            authors.append(name)

                    # Build URL from DOI or ID
                    doi = item_data.get("doi", "")
                    item_id = item_data.get("id", "")
                    url = f"https://doi.org/{doi}" if doi else f"https://chemrxiv.org/engage/chemrxiv/article-details/{item_id}"

                    paper = Paper(
                        title=item_data.get("title", "").replace("\n", " "),
                        authors=authors,
                        abstract=item_data.get("abstract", ""),
                        url=url,
                        source="ChemRxiv",
                        categories=[cat.get("name", "") for cat in item_data.get("categories", [])],
                        published=item_data.get("publishedDate", ""),
                    )
                    papers.append(paper)

                # Check if more pages
                if len(items) < limit:
                    break
                skip += limit

            except Exception as e:
                print(f"Error fetching ChemRxiv: {e}")
                break

        return papers

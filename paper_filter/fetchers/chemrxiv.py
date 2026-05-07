"""ChemRxiv metadata via Crossref.

ChemRxiv's own API (chemrxiv.org/engage/chemrxiv/public-api/v1) is gated by
Cloudflare since the 2026-01-21 migration to Wiley's Research Exchange
Preprints platform, so headless clients get HTTP 403. Crossref indexes every
ChemRxiv preprint by DOI prefix (10.26434) and has no bot protection in the
way, so we route through there instead.

Caveat: Crossref does not carry ChemRxiv abstracts. ChemRxiv is added to
NO_ABSTRACT_JOURNALS in filters/llm.py so the LLM scoring prompt knows to
judge these on the title alone.
"""

import re
from datetime import datetime, timedelta

import requests

from ..models import Paper
from .base import FeedFetcher


class ChemrxivFetcher(FeedFetcher):
    """Fetch ChemRxiv preprint metadata from Crossref by DOI prefix."""

    BASE_URL = "https://api.crossref.org/works"
    CHEMRXIV_PREFIX = "10.26434"
    # The mailto in the User-Agent puts us in Crossref's "polite pool" (faster,
    # more reliable). Update the email if you want bounce notifications.
    USER_AGENT = (
        "atomistic-simulation-paper-feed/0.1 "
        "(https://github.com/mcox3406/atomistic-simulation-paper-feed; "
        "mailto:noreply@example.com)"
    )

    def fetch(self) -> list[Paper]:
        """Fetch ChemRxiv preprints posted in the last 2 days."""
        date_from = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        date_to = datetime.now().strftime("%Y-%m-%d")
        print(f"  ChemRxiv: fetching papers from {date_from} to {date_to} via Crossref")

        papers = []
        cursor = "*"
        while True:
            try:
                response = requests.get(
                    self.BASE_URL,
                    params={
                        "filter": (
                            f"prefix:{self.CHEMRXIV_PREFIX},"
                            f"from-posted-date:{date_from},"
                            f"until-posted-date:{date_to}"
                        ),
                        "rows": 1000,
                        "cursor": cursor,
                        "select": "DOI,title,author,posted,URL,subject",
                    },
                    headers={"User-Agent": self.USER_AGENT},
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json().get("message", {})
                items = data.get("items", [])
                if not items:
                    break
                for item in items:
                    paper = self._item_to_paper(item)
                    if paper is not None:
                        papers.append(paper)
                next_cursor = data.get("next-cursor")
                if not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor
            except Exception as e:
                print(f"Error fetching ChemRxiv via Crossref: {e}")
                break

        return papers

    def _item_to_paper(self, item: dict) -> Paper | None:
        title_list = item.get("title") or []
        title = title_list[0].replace("\n", " ").strip() if title_list else ""
        if not title:
            return None

        authors = []
        for a in item.get("author", []):
            name = f"{a.get('given', '')} {a.get('family', '')}".strip()
            if name:
                authors.append(name)

        url = item.get("URL") or f"https://doi.org/{item.get('DOI', '')}"

        # CrossRef date-parts: [[2026, 5, 3]] → "2026-05-03". Partial dates
        # like [[2026, 5]] become "2026-05"; missing dates become "".
        date_parts = ((item.get("posted") or {}).get("date-parts") or [[]])[0]
        if date_parts:
            published = "-".join(
                f"{p:02d}" if i > 0 else str(p) for i, p in enumerate(date_parts)
            )
        else:
            published = ""

        subject = item.get("subject")
        categories = subject if isinstance(subject, list) else []

        return Paper(
            title=title,
            authors=authors,
            abstract="",
            url=url,
            source="ChemRxiv",
            categories=categories,
            published=published,
            version=self._extract_version(item.get("DOI", "")),
        )

    @staticmethod
    def _extract_version(doi: str) -> int | None:
        """ChemRxiv DOIs end in /v1, /v2, etc. when versioned."""
        match = re.search(r"/v(\d+)$", doi)
        if match:
            return int(match.group(1))
        return None

"""OpenReview workshop paper fetcher."""

import os
from datetime import datetime, timezone

import openreview

from ..models import Paper
from .base import FeedFetcher


class OpenReviewFetcher(FeedFetcher):
    """Fetch accepted papers from OpenReview workshops."""

    def __init__(self, workshop_venue_ids: list[str] | None = None):
        self.workshop_venue_ids = workshop_venue_ids or []

    def _get_client(self) -> openreview.api.OpenReviewClient:
        username = os.environ.get("OPENREVIEW_USERNAME", "")
        password = os.environ.get("OPENREVIEW_PASSWORD", "")
        if not username or not password:
            raise ValueError(
                "OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD environment variables are required"
            )
        return openreview.api.OpenReviewClient(
            baseurl="https://api2.openreview.net",
            username=username,
            password=password,
        )

    def fetch(self) -> list[Paper]:
        if not self.workshop_venue_ids:
            return []

        try:
            client = self._get_client()
        except ValueError as e:
            print(f"  OpenReview auth error: {e}")
            return []
        except Exception as e:
            print(f"  OpenReview connection error: {e}")
            return []

        papers = []
        for venue_id in self.workshop_venue_ids:
            try:
                notes = client.get_all_notes(content={"venueid": venue_id})
                for note in notes:
                    content = note.content or {}
                    title = content.get("title", {}).get("value", "")
                    authors = content.get("authors", {}).get("value", [])
                    abstract = content.get("abstract", {}).get("value", "")
                    keywords = content.get("keywords", {}).get("value", [])

                    if not title:
                        continue

                    forum_id = note.forum or note.id
                    url = f"https://openreview.net/forum?id={forum_id}"

                    # Extract human-readable workshop name from venue content or venue_id
                    venue_name = content.get("venue", {}).get("value", venue_id)

                    # Build direct PDF link if available
                    pdf_path = content.get("pdf", {}).get("value")
                    pdf_url = f"https://openreview.net{pdf_path}" if pdf_path else None

                    paper = Paper(
                        title=title.replace("\n", " "),
                        authors=authors if isinstance(authors, list) else [],
                        abstract=abstract,
                        url=url,
                        source=f"OpenReview: {venue_name}",
                        categories=keywords if isinstance(keywords, list) else [],
                        published=self._format_timestamp(note.cdate),
                        pdf_url=pdf_url,
                    )
                    papers.append(paper)

                print(f"  Workshop {venue_id}: {len(notes)} accepted papers")
            except Exception as e:
                print(f"  Error fetching workshop {venue_id}: {e}")

        # Deduplicate by URL
        seen = set()
        unique = []
        for p in papers:
            if p.url not in seen:
                seen.add(p.url)
                unique.append(p)
        return unique

    @staticmethod
    def _format_timestamp(cdate) -> str:
        """Convert OpenReview epoch-millisecond timestamp to ISO date string."""
        if not cdate:
            return ""
        try:
            return datetime.fromtimestamp(cdate / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, TypeError, OSError):
            return ""

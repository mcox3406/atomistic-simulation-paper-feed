"""Paper fetchers for various academic sources."""

from .base import FeedFetcher
from .arxiv import ArxivFetcher
from .biorxiv import BiorxivFetcher
from .chemrxiv import ChemrxivFetcher
from .journals import JournalRSSFetcher, SpringerNatureFetcher
from .openreview import OpenReviewFetcher

__all__ = [
    "FeedFetcher",
    "ArxivFetcher",
    "BiorxivFetcher",
    "ChemrxivFetcher",
    "JournalRSSFetcher",
    "SpringerNatureFetcher",
    "OpenReviewFetcher",
]

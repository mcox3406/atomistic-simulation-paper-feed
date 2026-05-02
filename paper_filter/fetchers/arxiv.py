"""arXiv RSS feed fetcher."""

import re

import feedparser

from ..models import Paper
from .base import FeedFetcher


class ArxivFetcher(FeedFetcher):
    """Fetch from arXiv RSS feeds by category."""

    CATEGORIES = [
        "physics.chem-ph",    # Chemical Physics
        "cond-mat.mtrl-sci",  # Materials Science
        "physics.comp-ph",    # Computational Physics
        "cond-mat.stat-mech", # Statistical Mechanics (MD/sampling)
        "cs.LG",              # Machine Learning (MLIPs, generative models)
        "stat.ML",            # Machine Learning (stats / theory)
    ]

    def fetch(self) -> list[Paper]:
        papers = []
        for category in self.CATEGORIES:
            url = f"https://rss.arxiv.org/rss/{category}"
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    cats = [tag.term for tag in entry.get("tags", [])]
                    paper_url = entry.get("link", "")

                    paper = Paper(
                        title=entry.get("title", "").replace("\n", " "),
                        authors=self._parse_authors(entry),
                        abstract=entry.get("summary", ""),
                        url=paper_url,
                        source="arXiv",
                        categories=cats if cats else [category],
                        published=entry.get("published", ""),
                        version=self._extract_version(entry.get("id", "")),
                    )
                    papers.append(paper)
            except Exception as e:
                print(f"Error fetching arXiv {category}: {e}")

        # Deduplicate by URL
        seen = set()
        unique = []
        for p in papers:
            if p.url not in seen:
                seen.add(p.url)
                unique.append(p)
        return unique

    def _parse_authors(self, entry) -> list[str]:
        authors = entry.get("authors", [])
        if authors:
            # Check if multiple authors in list vs single concatenated
            if len(authors) > 1:
                # Multiple separate author entries - extract each name
                return [a.get("name", str(a)) for a in authors if a.get("name")]
            else:
                # Single entry - may be concatenated, try splitting
                name = authors[0].get("name", str(authors[0]))
                return self._split_author_string(name)
        author = entry.get("author", "")
        if author:
            return self._split_author_string(author)
        return []

    def _split_author_string(self, author_str: str) -> list[str]:
        """Split a comma/and separated author string into list."""
        if not author_str:
            return []
        # Replace " and " with comma for uniform splitting
        author_str = author_str.replace(" and ", ", ")
        return [a.strip() for a in author_str.split(",") if a.strip()]

    def _extract_version(self, guid: str) -> int | None:
        """Extract version from arXiv guid (e.g., 'oai:arXiv.org:2602.00012v1')."""
        # Match arXiv paper ID pattern: YYMM.NNNNN followed by version
        match = re.search(r"\d{4}\.\d{4,5}v(\d+)", guid)
        if match:
            return int(match.group(1))
        return None

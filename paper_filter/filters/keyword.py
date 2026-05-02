"""Keyword-based first-pass filter."""

import re

from ..models import Paper


class KeywordFilter:
    """First-pass keyword filter to reduce volume before LLM scoring."""

    def __init__(self, keywords: list[str]):
        # Compile patterns for efficiency
        self.patterns = [
            re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE)
            for kw in keywords
        ]

    def matches(self, paper: Paper) -> bool:
        """Check if paper matches any keyword."""
        text = f"{paper.title} {paper.abstract}"
        return any(p.search(text) for p in self.patterns)

    def filter(self, papers: list[Paper]) -> list[Paper]:
        """Filter papers by keyword match."""
        return [p for p in papers if self.matches(p)]

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


_CORRECTION_PREFIXES = (
    "correction to",
    "correction:",
    "correction.",
    "erratum to",
    "erratum:",
    "erratum.",
    "retraction notice:",
    "retraction:",
    "publisher correction:",
    "author correction:",
    "addendum to",
    "addendum:",
)


def is_correction_or_erratum(title: str) -> bool:
    """True if this title is a correction/erratum/retraction notice, not a paper.

    Catches ACS "[ASAP] Correction to...", Nature "Publisher Correction:", and
    generic "Erratum:" / "Retraction:". These are noise: the titles sound
    atomistic, abstracts are missing, and the LLM scores them high without
    realizing they aren't real papers.
    """
    if not title:
        return False
    t = title.strip()
    # Strip ACS-style square-bracket prefixes ("[ASAP]", "[Article]", etc.).
    if t.startswith("[") and "]" in t:
        t = t.split("]", 1)[1].strip()
    t_lower = t.lower()
    return any(t_lower.startswith(p) for p in _CORRECTION_PREFIXES)

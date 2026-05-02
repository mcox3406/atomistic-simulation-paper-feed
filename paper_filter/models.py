"""Data models for the paper filter."""

import hashlib
from dataclasses import dataclass


@dataclass
class Paper:
    """Represents an academic paper."""

    title: str
    authors: list[str]
    abstract: str
    url: str
    source: str
    categories: list[str]
    published: str
    version: int | None = None
    pdf_url: str | None = None

    @property
    def id(self) -> str:
        """Generate a unique ID based on URL hash."""
        return hashlib.md5(self.url.encode()).hexdigest()[:12]

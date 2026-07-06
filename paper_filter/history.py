"""Paper history tracking to avoid duplicate posts."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from .models import Paper


class PaperHistory:
    """Track papers we've already posted to avoid duplicates."""

    def __init__(self, history_file: str = "posted_papers.json"):
        self.history_file = Path(history_file)
        self.posted_ids = self._load_history()
        # Already-posted papers seen again in this run's feeds. Their history
        # dates get refreshed on save so entries expire 30 days after the paper
        # *last appeared* in a feed, not 30 days after first post. Without this,
        # OpenReview papers (which stay in the venue feed forever) fall out of
        # history after 30 days and get reposted.
        self._seen_posted_ids: set = set()

    def _load_history(self) -> set:
        if self.history_file.exists():
            with open(self.history_file) as f:
                data = json.load(f)
                cutoff = (datetime.now() - timedelta(days=30)).isoformat()
                return {pid for pid, date in data.items() if date > cutoff}
        return set()

    def _save_history(self, newly_posted_ids: set):
        # Re-read on save so we preserve original posted-on dates for IDs we already had.
        existing = {}
        if self.history_file.exists():
            with open(self.history_file) as f:
                existing = json.load(f)

        today = datetime.now().isoformat()
        for pid in newly_posted_ids | self._seen_posted_ids:
            existing[pid] = today

        # Prune entries not posted or seen in a feed for 30 days
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        existing = {k: v for k, v in existing.items() if v > cutoff}

        with open(self.history_file, "w") as f:
            json.dump(existing, f)

    def filter_new(self, papers: list[Paper]) -> list[Paper]:
        """Return only papers we haven't posted before."""
        new = []
        for p in papers:
            if p.id in self.posted_ids:
                self._seen_posted_ids.add(p.id)
            else:
                new.append(p)
        return new

    def mark_posted(self, papers: list[Paper]):
        """Mark papers as posted."""
        newly_posted = {p.id for p in papers}
        self.posted_ids |= newly_posted
        self._save_history(newly_posted)

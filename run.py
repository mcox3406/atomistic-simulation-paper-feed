#!/usr/bin/env python3
"""Entry point for the paper filter bot."""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # Load .env file if present

from paper_filter import run_pipeline


def sync_history():
    """Mark all currently fetchable papers as 'seen' without LLM filtering or posting."""
    from datetime import datetime
    from paper_filter.fetchers import (
        ArxivFetcher, BiorxivFetcher, ChemrxivFetcher,
        JournalRSSFetcher, SpringerNatureFetcher, OpenReviewFetcher
    )
    from paper_filter.pipeline import load_config

    config = load_config()
    min_if = config.get("min_impact_factor")
    max_age = config.get("max_age_hours")

    openreview_workshops = config.get("sources", {}).get("openreview_workshops", [])

    fetchers = [
        ArxivFetcher(),
        BiorxivFetcher(),
        ChemrxivFetcher(),
        SpringerNatureFetcher(min_impact_factor=min_if, max_age_hours=max_age),
        JournalRSSFetcher(min_impact_factor=min_if, max_age_hours=max_age),
        OpenReviewFetcher(workshop_venue_ids=openreview_workshops),
    ]

    print("Fetching papers to sync history...")
    all_papers = []
    for fetcher in fetchers:
        papers = fetcher.fetch()
        print(f"  {fetcher.__class__.__name__}: {len(papers)} papers")
        all_papers.extend(papers)

    # Load existing history
    history_file = Path("posted_papers.json")
    if history_file.exists():
        with open(history_file) as f:
            history = json.load(f)
    else:
        history = {}

    # Add all papers to history
    now = datetime.now().isoformat()
    added = 0
    for paper in all_papers:
        if paper.id not in history:
            history[paper.id] = now
            added += 1

    # Save
    with open(history_file, "w") as f:
        json.dump(history, f)

    print(f"Added {added} papers to history (total: {len(history)})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Filter and post relevant papers")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print results instead of posting to Slack",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: limit to 50 papers for quick/cheap testing",
    )
    parser.add_argument(
        "--sync-history",
        action="store_true",
        help="Mark all current papers as seen without filtering or posting",
    )
    parser.add_argument(
        "--no-slack",
        action="store_true",
        help="Suppress the Slack post. Still writes JSON, marks history, etc. (for backfilling)",
    )
    args = parser.parse_args()

    if args.sync_history:
        sync_history()
    else:
        run_pipeline(dry_run=args.dry_run, test_mode=args.test, no_slack=args.no_slack)

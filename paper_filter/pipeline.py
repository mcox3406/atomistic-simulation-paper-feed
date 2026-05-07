"""Main pipeline orchestration."""

import json
import os
from datetime import datetime
from pathlib import Path

from .fetchers import ArxivFetcher, BiorxivFetcher, ChemrxivFetcher, JournalRSSFetcher, OpenReviewFetcher, SpringerNatureFetcher
from .filters import KeywordFilter, LLMFilter, PaperCategorizer
from .filters.keyword import is_correction_or_erratum
from .filters.llm import InsufficientCreditsError
from .history import PaperHistory
from .key_authors import filter_papers_by_key_authors, get_key_authors_on_paper, load_key_authors
from .slack import SlackPoster
from .json_export import save_papers_to_json


def load_config() -> dict:
    """Load configuration from config.json."""
    config_path = Path(__file__).parent.parent / "config.json"
    with open(config_path) as f:
        return json.load(f)


def run_pipeline(dry_run: bool = False, test_mode: bool = False, no_slack: bool = False):
    """Run the full paper filtering pipeline.

    dry_run: skip ALL side effects (no Slack, no JSON, no history update).
    no_slack: skip only the Slack post. JSON + history still update.
              Useful for backfilling a day after a partial-failure run.
    """

    print(f"Starting paper filter pipeline at {datetime.now()}")
    if dry_run:
        print("DRY RUN MODE - no side effects")
    if test_mode:
        print("TEST MODE - limiting to 50 papers after keyword filter")
    if no_slack and not dry_run:
        print("NO-SLACK MODE - will write JSON and update history but skip the Slack post")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")

    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook_url and not dry_run and not no_slack:
        raise ValueError("SLACK_WEBHOOK_URL environment variable is required")

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

    keyword_filter = KeywordFilter(config["keywords"])

    llm_filter = LLMFilter(
        api_key=api_key,
        lab_description=config["lab_description"],
        threshold=config.get("relevance_threshold", 0.6),
        model=config.get("model"),
    )

    categorizer = PaperCategorizer(api_key=api_key, model=config.get("model"))

    # SlackPoster's dry_run=True suppresses the actual webhook call. Reuse that
    # for --no-slack so we don't need a parallel code path.
    slack_poster = SlackPoster(webhook_url, dry_run=dry_run or no_slack)

    history = PaperHistory()

    key_authors = load_key_authors()
    print(f"Loaded {len(key_authors)} key authors")

    print("Fetching papers from all sources...")
    all_papers = []
    for fetcher in fetchers:
        papers = fetcher.fetch()
        print(f"  {fetcher.__class__.__name__}: {len(papers)} papers")
        all_papers.extend(papers)

    print(f"Total fetched: {len(all_papers)} papers")

    new_papers = history.filter_new(all_papers)
    print(f"After deduplication: {len(new_papers)} new papers")

    # Drop corrections / errata / retraction notices before any other filter:
    # title-only feeds (ACS, Nature) make these look atomistic-relevant to the LLM.
    before = len(new_papers)
    new_papers = [p for p in new_papers if not is_correction_or_erratum(p.title)]
    skipped = before - len(new_papers)
    if skipped:
        print(f"Skipped {skipped} corrections/errata/retractions")

    # Key-author papers bypass both keyword and LLM filters.
    key_author_papers, other_papers = filter_papers_by_key_authors(new_papers, key_authors)
    if key_author_papers:
        print(f"Papers from key authors (bypass filtering): {len(key_author_papers)}")
        for paper in key_author_papers:
            authors_found = get_key_authors_on_paper(paper, key_authors)
            print(f"  - {paper.title[:60]}... ({', '.join(authors_found)})")

    keyword_matches = keyword_filter.filter(other_papers)
    print(f"After keyword filter: {len(keyword_matches)} papers")

    if test_mode and len(keyword_matches) > 50:
        keyword_matches = keyword_matches[:50]
        print(f"TEST MODE: limited to {len(keyword_matches)} papers")

    credits_exhausted = False
    if keyword_matches:
        print("Running LLM relevance scoring...")
        try:
            relevant_papers = llm_filter.filter(keyword_matches)
            print(f"After LLM filter: {len(relevant_papers)} papers")
        except InsufficientCreditsError:
            print("ERROR: API credits exhausted during LLM scoring")
            relevant_papers = []
            credits_exhausted = True
    else:
        relevant_papers = []

    # Re-attach key-author papers at score 1.0 so they sort to the top.
    for paper in key_author_papers:
        authors_found = get_key_authors_on_paper(paper, key_authors)
        reason = f"Key author: {', '.join(authors_found)}"
        relevant_papers.append((paper, 1.0, reason))

    if key_author_papers:
        print(f"Total relevant papers (including key authors): {len(relevant_papers)}")

    if relevant_papers:
        print("Categorizing papers by research area...")
        try:
            categorized_papers = categorizer.categorize(relevant_papers)
            for cat, papers in categorized_papers.items():
                if papers:
                    print(f"  {cat}: {len(papers)} papers")
        except InsufficientCreditsError:
            print("ERROR: API credits exhausted during categorization")
            categorized_papers = {"Atomistic Applications": relevant_papers}
            credits_exhausted = True
    else:
        categorized_papers = {}

    print("Posting to Slack...")
    slack_poster.post_papers(categorized_papers, credits_exhausted=credits_exhausted)

    # Export to static JSON for the web frontend (non-blocking).
    # Skipped in dry-run so the working tree stays clean, especially in --test
    # mode, which produces a partial dataset that should never be committed.
    if not dry_run:
        print("Exporting papers to JSON...")
        save_papers_to_json(categorized_papers)
    else:
        print("Skipping JSON export (dry run)")

    if not dry_run:
        history.mark_posted([p for p, _, _ in relevant_papers])


    print("Pipeline complete!")

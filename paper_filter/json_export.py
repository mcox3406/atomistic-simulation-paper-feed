"""Export papers to static JSON files for the web frontend.

Layout (under frontend/public/data/papers/):
    YYYY-MM-DD.json   — papers added on that date
    index.json        — list of {date, count}, newest first
"""

import json
from datetime import datetime
from pathlib import Path

from .key_authors import get_key_authors_on_paper, load_key_authors

DATA_DIR = Path(__file__).parent.parent / "frontend" / "public" / "data" / "papers"


def _paper_to_dict(paper, score: float, reason: str, category: str, key_authors: list[str], today: str) -> dict:
    paper_key_authors = get_key_authors_on_paper(paper, key_authors)
    return {
        "id": paper.id,
        "title": paper.title,
        "authors": paper.authors,
        "abstract": paper.abstract,
        "url": paper.url,
        "pdf_url": getattr(paper, "pdf_url", None),
        "source": paper.source,
        "categories": paper.categories,
        "published": paper.published if paper.published else None,
        "version": getattr(paper, "version", None),
        "added_date": today,
        "category": category,
        "relevance_score": score,
        "relevance_reason": reason,
        "key_authors": paper_key_authors if paper_key_authors else [],
    }


def save_papers_to_json(categorized_papers: dict) -> bool:
    """Write papers for today's run to ``data/papers/<today>.json`` and refresh ``index.json``.

    Returns True on success, False on error. Failures are logged but never raise.
    """
    today = datetime.now().date().isoformat()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    key_authors = load_key_authors()

    new_records = []
    for category, papers in categorized_papers.items():
        for paper, score, reason in papers:
            new_records.append(_paper_to_dict(paper, score, reason, category, key_authors, today))

    today_file = DATA_DIR / f"{today}.json"

    # If a file for today already exists (re-run), merge by paper id (keeping newer).
    existing = {}
    if today_file.exists():
        try:
            with open(today_file) as f:
                for rec in json.load(f):
                    existing[rec["id"]] = rec
        except Exception as e:
            print(f"  Warning: could not read existing {today_file.name}: {e}")

    for rec in new_records:
        existing[rec["id"]] = rec

    merged = sorted(existing.values(), key=lambda r: r.get("relevance_score", 0), reverse=True)

    try:
        with open(today_file, "w") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"  Failed to write {today_file}: {e}")
        return False

    # Refresh the index by scanning the directory.
    index = []
    for path in sorted(DATA_DIR.glob("*.json"), reverse=True):
        if path.name == "index.json":
            continue
        try:
            with open(path) as f:
                count = len(json.load(f))
            index.append({"date": path.stem, "count": count})
        except Exception as e:
            print(f"  Warning: could not read {path.name} for index: {e}")

    try:
        with open(DATA_DIR / "index.json", "w") as f:
            json.dump(index, f, indent=2)
    except Exception as e:
        print(f"  Failed to write index.json: {e}")
        return False

    print(f"  Wrote {len(merged)} papers to {today_file.name} (index has {len(index)} dates)")
    return True

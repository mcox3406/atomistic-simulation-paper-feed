"""Slack webhook integration."""

from datetime import datetime

import requests

from .filters.categorizer import CATEGORIES
from .key_authors import is_key_author, load_key_authors
from .models import Paper

# High-volume venues suppressed from Slack to keep the daily digest readable.
# The web frontend still serves them (gated behind a toggle).
HIGH_VOLUME_SOURCES = frozenset({
    "Comp. Mat. Sci.",
    "Phys. Rev. Materials",
    "PCCP",
})



class SlackPoster:
    """Post papers to Slack via webhook."""

    def __init__(self, webhook_url: str, dry_run: bool = False):
        self.webhook_url = webhook_url
        self.dry_run = dry_run
        self.key_authors = load_key_authors()

    def post_papers(self, categorized_papers: dict[str, list[tuple[Paper, float, str]]], credits_exhausted: bool = False):
        """Post categorized papers to Slack."""

        # Suppress high-volume venues, but keep key-author hits regardless of source.
        filtered = {}
        for cat, papers in categorized_papers.items():
            kept = [
                (p, s, r) for p, s, r in papers
                if p.source not in HIGH_VOLUME_SOURCES or r.startswith("Key author:")
            ]
            if kept:
                filtered[cat] = kept
        categorized_papers = filtered

        total = sum(len(papers) for papers in categorized_papers.values())

        if total == 0 and not credits_exhausted:
            self._post_message(
                {"text": "*Atomistic Simulation Paper Feed*\nNo relevant papers found today."}
            )
            return

        if total == 0 and credits_exhausted:
            self._post_message(
                {"text": ":warning: *Atomistic Simulation Paper Feed*\nAPI credits exhausted - could not filter papers today. Please top up credits."}
            )
            return

        # Categories whose paper list overflows Slack's 3000-char block limit
        # get sent as follow-up messages after the main one.
        overflow_messages = []
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Atomistic Simulation Paper Feed — {datetime.now().strftime('%B %d, %Y')}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Found *{total}* relevant papers in the last 24 hours",
                    }
                ],
            },
        ]

        if credits_exhausted:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":warning: *API credits exhausted* - only showing key author papers. Regular filtering was skipped.",
                },
            })

        blocks.append({"type": "divider"})

        for category in CATEGORIES:
            papers = categorized_papers.get(category, [])
            if not papers:
                continue

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{category}* ({len(papers)})",
                    },
                }
            )

            papers_sorted = sorted(papers, key=lambda x: x[1], reverse=True)
            paper_lines = []
            for paper, score, reason in papers_sorted:
                title = self._escape_mrkdwn(paper.title)
                # Show vN for arXiv so updated papers are visibly distinct from the v1 we already posted.
                if paper.version is not None:
                    title = f"{title} (v{paper.version})"
                authors_str = self._format_authors(paper.authors)
                pdf_link = f" <{paper.pdf_url}|[pdf]>" if paper.pdf_url else ""
                if authors_str:
                    paper_lines.append(f"• <{paper.url}|{title}>{pdf_link} - {authors_str} ({paper.source})")
                else:
                    paper_lines.append(f"• <{paper.url}|{title}>{pdf_link} ({paper.source})")

            chunks = self._chunk_lines(paper_lines, max_chars=2800)

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": chunks[0],
                    },
                }
            )

            for i, chunk in enumerate(chunks[1:], start=2):
                overflow_messages.append({
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*{category}* (continued {i}/{len(chunks)})",
                            },
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": chunk,
                            },
                        },
                    ]
                })

        self._post_message({"blocks": blocks})

        for overflow in overflow_messages:
            self._post_message(overflow)

    def _chunk_lines(self, lines: list[str], max_chars: int = 2800) -> list[str]:
        """Split lines into chunks that fit within Slack's character limit."""
        if not lines:
            return ["_No papers_"]

        chunks = []
        current_chunk = ""

        for line in lines:
            if current_chunk and len(current_chunk) + len(line) + 1 > max_chars:
                chunks.append(current_chunk.rstrip("\n"))
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"

        if current_chunk:
            chunks.append(current_chunk.rstrip("\n"))

        return chunks

    def _escape_mrkdwn(self, text: str) -> str:
        """Escape special characters for Slack mrkdwn."""
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        return text

    def _format_authors(self, authors: list[str], max_authors: int = 10) -> str:
        """
        Format author list for Slack display.

        Bold key authors. If the list is longer than max_authors, truncate with
        ellipses but keep: the first N-1, the last author, and any key authors
        that would otherwise be hidden in the middle of the list.
        """
        if not authors:
            return ""

        def format_author(name: str) -> str:
            escaped = self._escape_mrkdwn(name)
            if is_key_author(name, self.key_authors):
                return f"*{escaped}*"
            return escaped

        if len(authors) <= max_authors:
            return ", ".join(format_author(a) for a in authors)

        shown_indices = set(range(max_authors - 1))
        shown_indices.add(len(authors) - 1)
        for i, author in enumerate(authors):
            if is_key_author(author, self.key_authors):
                shown_indices.add(i)

        sorted_indices = sorted(shown_indices)
        parts = []
        prev_idx = -1
        for idx in sorted_indices:
            if prev_idx >= 0 and idx > prev_idx + 1:
                parts.append("...")
            parts.append(format_author(authors[idx]))
            prev_idx = idx

        return ", ".join(parts)

    def _post_message(self, payload: dict):
        """Send a message to Slack (or print if dry_run)."""
        # Dump the most recent payload to disk so failed posts can be replayed manually.
        import json
        with open("slack_payload.json", "w") as f:
            json.dump(payload, f, indent=2)

        if self.dry_run:
            print("\n" + "=" * 60)
            print("DRY RUN - Would post to Slack:")
            print("=" * 60)
            if "text" in payload:
                print(payload["text"])
            if "blocks" in payload:
                for block in payload["blocks"]:
                    if block.get("type") == "header":
                        print(f"\n{block['text']['text']}")
                    elif block.get("type") == "context":
                        print(block["elements"][0]["text"])
                    elif block.get("type") == "section":
                        print(block["text"]["text"])
                    elif block.get("type") == "divider":
                        print("-" * 40)
            print("=" * 60 + "\n")
            return

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
        except Exception as e:
            print(f"Error posting to Slack: {e}")

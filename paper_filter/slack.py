"""Slack webhook integration."""

from datetime import datetime

import requests

from .filters.categorizer import CATEGORIES
from .key_authors import is_key_author, load_key_authors
from .models import Paper



class SlackPoster:
    """Post papers to Slack via webhook."""

    def __init__(self, webhook_url: str, dry_run: bool = False):
        self.webhook_url = webhook_url
        self.dry_run = dry_run
        self.key_authors = load_key_authors()

    def post_papers(self, categorized_papers: dict[str, list[tuple[Paper, float, str]]], credits_exhausted: bool = False):
        """Post categorized papers to Slack."""

        # Count total papers
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

        # Build message blocks
        overflow_messages = []  # Additional messages for categories that overflow
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

        # Add warning if credits exhausted
        if credits_exhausted:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":warning: *API credits exhausted* - only showing key author papers. Regular filtering was skipped.",
                },
            })

        blocks.append({"type": "divider"})

        # Add each category with papers
        for category in CATEGORIES:
            papers = categorized_papers.get(category, [])
            if not papers:
                continue

            # Category header
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{category}* ({len(papers)})",
                    },
                }
            )

            # Paper list - sort by score descending
            papers_sorted = sorted(papers, key=lambda x: x[1], reverse=True)
            paper_lines = []
            for paper, score, reason in papers_sorted:
                # Escape special characters for Slack mrkdwn
                title = self._escape_mrkdwn(paper.title)
                # Append version for arXiv papers (helps identify updated papers)
                if paper.version is not None:
                    title = f"{title} (v{paper.version})"
                # Format authors
                authors_str = self._format_authors(paper.authors)
                pdf_link = f" <{paper.pdf_url}|[pdf]>" if paper.pdf_url else ""
                if authors_str:
                    paper_lines.append(f"• <{paper.url}|{title}>{pdf_link} - {authors_str} ({paper.source})")
                else:
                    paper_lines.append(f"• <{paper.url}|{title}>{pdf_link} ({paper.source})")

            # Split paper lines into chunks respecting Slack's 3000 char limit
            chunks = self._chunk_lines(paper_lines, max_chars=2800)

            # First chunk goes in main message
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": chunks[0],
                    },
                }
            )

            # Additional chunks get posted as overflow messages later
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

        # Post main message
        self._post_message({"blocks": blocks})

        # Post any overflow messages
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
                # Start a new chunk
                chunks.append(current_chunk.rstrip("\n"))
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(current_chunk.rstrip("\n"))

        return chunks

    def _escape_mrkdwn(self, text: str) -> str:
        """Escape special characters for Slack mrkdwn."""
        # Replace & < > with HTML entities
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        return text

    def _format_authors(self, authors: list[str], max_authors: int = 10) -> str:
        """
        Format author list for Slack display.

        - Bold key authors
        - If more than max_authors, truncate with ellipsis but keep final author
        - Key authors are NEVER truncated - they're always shown even if in the
          middle of a long list
          e.g., "A1, A2, ..., *KeyAuthor*, ..., LastAuthor"
        """
        if not authors:
            return ""

        # Format each author, bolding key authors
        def format_author(name: str) -> str:
            escaped = self._escape_mrkdwn(name)
            if is_key_author(name, self.key_authors):
                return f"*{escaped}*"
            return escaped

        if len(authors) <= max_authors:
            return ", ".join(format_author(a) for a in authors)

        # Determine which author indices to show:
        # 1. First (max_authors - 1) authors
        # 2. Last author
        # 3. Any key authors that would otherwise be hidden
        shown_indices = set(range(max_authors - 1))  # First N-1 (e.g., 0-8)
        shown_indices.add(len(authors) - 1)  # Last author

        # Add any key authors that would be truncated
        for i, author in enumerate(authors):
            if is_key_author(author, self.key_authors):
                shown_indices.add(i)

        # Build the formatted string, inserting ellipses where there are gaps
        sorted_indices = sorted(shown_indices)
        parts = []
        prev_idx = -1

        for idx in sorted_indices:
            if prev_idx >= 0 and idx > prev_idx + 1:
                # There's a gap - authors were skipped
                parts.append("...")
            parts.append(format_author(authors[idx]))
            prev_idx = idx

        return ", ".join(parts)

    def _post_message(self, payload: dict):
        """Send a message to Slack (or print if dry_run)."""
        # Always save payload for debugging/reuse
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

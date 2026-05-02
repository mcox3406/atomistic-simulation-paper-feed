"""Paper Filter Bot - Modular package for filtering academic papers."""

from .models import Paper
from .history import PaperHistory
from .slack import SlackPoster
from .pipeline import run_pipeline
from .json_export import save_papers_to_json

__all__ = ["Paper", "PaperHistory", "SlackPoster", "run_pipeline", "save_papers_to_json"]

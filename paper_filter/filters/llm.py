"""LLM-based relevance scoring filter."""

import json
import re

from anthropic import Anthropic
from tqdm import tqdm

from ..models import Paper

# Journals that don't include abstracts in their RSS feeds
NO_ABSTRACT_JOURNALS = {
    'JACS', 'JCIM', 'JCTC', 'ACS Central Science',
    'J. Med. Chem.', 'ACS Catalysis', 'J. Org. Chem.', 'Org. Lett.'
}


class InsufficientCreditsError(Exception):
    """Raised when API credits are depleted."""
    pass


class LLMFilter:
    """Second-pass LLM-based relevance scoring."""

    # Default model - can be overridden via config
    DEFAULT_MODEL = "claude-haiku-4-5-20251001"

    def __init__(
        self,
        api_key: str,
        lab_description: str,
        threshold: float = 0.6,
        model: str = None,
    ):
        self.client = Anthropic(api_key=api_key)
        self.lab_description = lab_description
        self.threshold = threshold
        self.model = model or self.DEFAULT_MODEL

    def score_papers(self, papers: list[Paper]) -> list[tuple[Paper, float, str]]:
        """Score papers for relevance. Returns (paper, score, reason) tuples."""
        if not papers:
            return []

        results = []

        # Process in batches to reduce API calls
        batch_size = 10

        with tqdm(total=len(papers), desc="Scoring papers", unit="paper") as pbar:
            for i in range(0, len(papers), batch_size):
                batch = papers[i : i + batch_size]
                batch_results = self._score_batch(batch)
                results.extend(batch_results)
                pbar.update(len(batch))

        return results

    def _score_batch(self, papers: list[Paper]) -> list[tuple[Paper, float, str]]:
        """Score a batch of papers."""
        papers_text = ""
        has_no_abstract_papers = False
        for idx, paper in enumerate(papers):
            abstract = paper.abstract[:1500] if paper.abstract else ""
            if paper.source in NO_ABSTRACT_JOURNALS and not abstract:
                has_no_abstract_papers = True
            papers_text += f"""
---
Paper {idx + 1}:
Title: {paper.title}
Source: {paper.source}
Abstract: {abstract if abstract else "(not available)"}
---
"""

        no_abstract_note = ""
        if has_no_abstract_papers:
            no_abstract_note = """
IMPORTANT: Some papers are from peer-reviewed journals (JACS, JCIM, JCTC, etc.) whose RSS feeds do not include abstracts. For these papers, evaluate relevance based on the title alone. Since these are established, peer-reviewed journals, give the benefit of the doubt if the title suggests relevance to the lab's research areas - a relevant-sounding title from these journals should score similarly to a paper with a matching abstract.
"""

        prompt = f"""You are a strict filter for an atomistic-simulation paper feed. Your job is to score each paper from 0.0 to 1.0 for fit. Default to caution: a missed paper is cheap, a false positive is expensive.

Lab Focus: {self.lab_description}
{no_abstract_note}
HARD TEST. A paper qualifies as ATOMISTIC SIMULATION work only if ALL of the following hold:
  (a) The system being studied is represented as explicit atoms (or coarse-grained beads tied to an atomistic mapping), not just SMILES, 2D graphs, fingerprints, sequence, or compositional features.
  (b) The methodology involves at least one of: molecular dynamics; Monte Carlo on atoms; geometry optimization; transition-state / NEB; free-energy methods; classical force fields; semi-empirical / tight-binding; DFT; post-HF; OR the development, training, or benchmarking of a machine-learned interatomic potential / force field used for any of the above.
  (c) The paper's contribution either advances one of those methods, or applies one of them to learn something about a chemical / material / biological system.

If a paper fails ANY of (a)-(c), score it strictly below 0.5, no matter how many surface-level keywords match.

Scoring rubric (use these as anchors):
  - MLIP development, training, benchmarking, or applied MLIP-driven simulation → 0.85–0.95
  - Classical / ab initio MD methods or applications on real atomic systems → 0.75–0.9
  - Free-energy / enhanced-sampling method or application → 0.75–0.9
  - DFT / post-HF / semi-empirical method development; embedding theories → 0.75–0.9
  - DFT/MLIP-driven CSP, polymorph search, materials discovery with explicit atomistic calculations → 0.75–0.9
  - Generative model that outputs 3D atomic configurations AND is tied to / validated by a potential → 0.7–0.85
  - Equivariant / geometric / diffusion / flow-matching method WITH atomistic application or energetic validation → 0.7–0.85
  - Single-molecule quantum chemistry calculation as a mechanistic study (no MD, no method advance) → 0.4–0.6 (borderline, lean low)
  - Generative model that outputs only SMILES, compositions, or 2D graphs → 0.2–0.4
  - Pure ML methodology (architectures, diffusion, equivariance) with no atomistic application or validation → 0.1–0.3
  - LLM agent / orchestration / "AI-assisted" workflow that does not itself run simulations → 0.05–0.2
  - High-throughput screening with only descriptors / fingerprints / compositional rules → 0.1–0.3
  - XRD / diffraction inverse problem, structure refinement without atomistic dynamics → 0.1–0.3
  - Drug docking / virtual screening of drug-like libraries / ADMET → 0.0–0.2
  - Retrosynthesis, reaction-outcome, mass spectrometry, AlphaFold-style structure prediction → 0.0–0.2
  - Protein design or biology paper without explicit atomistic simulation methodology → 0.0–0.2

Below are {len(papers)} papers. For each, give a score 0.0–1.0 with a one-sentence reason that names the methodology and explicitly states whether (a)–(c) are satisfied.

{papers_text}

Respond in JSON format:
{{
    "scores": [
        {{"paper": 1, "score": 0.85, "reason": "..."}},
        {{"paper": 2, "score": 0.20, "reason": "..."}},
        ...
    ]
}}

When uncertain, score lower."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
                scores = data.get("scores", [])

                results = []
                for score_data in scores:
                    idx = score_data["paper"] - 1
                    if 0 <= idx < len(papers):
                        results.append(
                            (
                                papers[idx],
                                score_data["score"],
                                score_data.get("reason", ""),
                            )
                        )
                return results

        except Exception as e:
            error_str = str(e)
            # Credit-balance failures should halt the whole run; everything else
            # falls through to a neutral 0.5 so a transient API blip isn't fatal.
            if "credit balance is too low" in error_str.lower():
                raise InsufficientCreditsError("API credit balance is too low to continue scoring")
            print(f"Error scoring batch: {e}")

        return [(p, 0.5, "Error during scoring") for p in papers]

    def filter(self, papers: list[Paper]) -> list[tuple[Paper, float, str]]:
        """Filter papers above threshold."""
        scored = self.score_papers(papers)
        return [(p, s, r) for p, s, r in scored if s >= self.threshold]

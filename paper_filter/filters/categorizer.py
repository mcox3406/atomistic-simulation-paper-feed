"""LLM-based paper categorization."""

import json
import re

from anthropic import Anthropic
from tqdm import tqdm

from ..models import Paper
from .llm import InsufficientCreditsError

CATEGORIES = [
    "MLIPs & Foundation Models",
    "Molecular Dynamics & Sampling",
    "Electronic Structure",
    "Generative & Geometric ML for Atoms",
    "Materials Discovery & High-Throughput",
    "Atomistic Applications",
]


class PaperCategorizer:
    """Categorize papers into research areas using LLM."""

    DEFAULT_MODEL = "claude-haiku-4-5-20251001"

    def __init__(self, api_key: str, model: str = None):
        self.client = Anthropic(api_key=api_key)
        self.model = model or self.DEFAULT_MODEL

    def categorize(
        self, papers: list[tuple[Paper, float, str]]
    ) -> dict[str, list[tuple[Paper, float, str]]]:
        """Categorize papers into research areas. Returns dict of category -> papers."""
        if not papers:
            return {cat: [] for cat in CATEGORIES}

        # Get categories for all papers
        paper_categories = self._categorize_batch(papers)

        # Group by category
        result = {cat: [] for cat in CATEGORIES}
        for (paper, score, reason), category in zip(papers, paper_categories):
            if category in result:
                result[category].append((paper, score, reason))
            else:
                # If the LLM emits a string we don't recognize, route to Applications.
                # These are post-filter atomistic papers, so the most likely garbage
                # is a system-specific paper the model couldn't pin to a method bucket.
                result["Atomistic Applications"].append((paper, score, reason))

        return result

    def _categorize_batch(
        self, papers: list[tuple[Paper, float, str]]
    ) -> list[str]:
        """Categorize a batch of papers."""
        categories_list = "\n".join(f"- {cat}" for cat in CATEGORIES)

        # Format papers
        papers_text = ""
        for idx, (paper, score, reason) in enumerate(papers):
            papers_text += f"{idx + 1}. {paper.title} ({paper.source})\n"

        prompt = f"""Categorize each paper into exactly one of these six research areas. Every paper has already passed a strict atomistic-simulation relevance filter, so all six buckets assume that context.

{categories_list}

Papers to categorize:
{papers_text}

Bucket definitions:
- "MLIPs & Foundation Models": development, training-data strategies, benchmarks, transferability, or fine-tuning of machine-learned interatomic potentials (NequIP, MACE, Allegro, SchNet, GemNet, PaiNN, MatterSim, UMA, eSEN, Orb, GNoME, ANI, AIMNet, etc.). Application papers that happen to use an MLIP go elsewhere — this bucket is about the potential itself.
- "Molecular Dynamics & Sampling": classical or ab initio MD, free-energy methods (metadynamics, umbrella sampling, replica exchange, thermodynamic integration, alchemical), enhanced sampling, coarse-graining, learned samplers / Boltzmann generators, path-integral MD, kinetic Monte Carlo. Includes statistical-mechanics theory for simulated ensembles.
- "Electronic Structure": DFT and exchange-correlation development, GW/BSE, post-Hartree-Fock methods (CCSD, MP2), embedding theories (QM/MM, DMFT), semi-empirical / tight-binding (DFTB, GFN-xTB), automated DFT workflows, methodological work tied to electronic-structure codes (VASP, CP2K, Quantum ESPRESSO, ORCA, Psi4, GPAW).
- "Generative & Geometric ML for Atoms": generative models for 3D atomic systems (diffusion, flow matching, autoregressive crystal or molecule generation) AND equivariant / geometric architectures whose central contribution is the model itself, not its application.
- "Materials Discovery & High-Throughput": crystal structure prediction, polymorph search, high-throughput DFT/MLIP screening, active learning or Bayesian optimization campaigns. The contribution is the search and what it found — breadth.
- "Atomistic Applications": mechanistic and property studies of specific systems — catalysis mechanisms, battery cathodes/electrolytes, defect physics, surface and adsorption studies, MOF / perovskite / 2D-material characterization. The contribution is understanding a specific material or process — depth.

Seam rules for borderline cases:
- 4 vs 5 (Generative ML vs Discovery): "Did the paper build a generative model?" vs "Did the paper run a search?". A generative model used as part of a discovery campaign goes to 5 if the paper's pitch is the discovery, 4 if the pitch is the model.
- 5 vs 6 (Discovery vs Applications): breadth vs depth. Screening many systems → 5. Studying one or a few in detail → 6.
- 1 vs 6 (MLIPs vs Applications): "Is the contribution the potential or the chemistry?" An MLIP fine-tuned to study a specific catalyst goes to 1 if the paper pitches the potential, 6 if it pitches the chemistry.

Pick the best single bucket per paper.

Respond with a JSON array of category names in the same order as the papers:
{{"categories": ["Category1", "Category2", ...]}}"""

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
                categories = data.get("categories", [])
                # Validate and pad if needed
                while len(categories) < len(papers):
                    categories.append("Other")
                return categories[:len(papers)]

        except Exception as e:
            error_str = str(e)
            if "credit balance is too low" in error_str.lower():
                raise InsufficientCreditsError("API credit balance is too low to categorize papers")
            print(f"Error categorizing papers: {e}")

        # Fallback: all unclassified -> caught by Atomistic Applications in caller
        return ["Atomistic Applications"] * len(papers)

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
    "DFT & Quantum Chemistry",
    "Materials Discovery & Generative Models",
    "Methods & Theory",
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
                # Unknown / unmapped categories fall into Methods & Theory as a catch-all
                result["Methods & Theory"].append((paper, score, reason))

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

        prompt = f"""Categorize each paper into exactly one of these research areas:

{categories_list}

Papers to categorize:
{papers_text}

Guidelines:
- "MLIPs & Foundation Models": machine-learned interatomic potentials, neural network potentials, equivariant GNNs trained on energies/forces, universal/foundation potentials (NequIP, MACE, Allegro, SchNet, GemNet, PaiNN, MatterSim, UMA, eSEN, Orb, GNoME, ANI, AIMNet); training-data strategies, transferability, benchmarks for ML potentials.
- "Molecular Dynamics & Sampling": classical or ab initio MD, free-energy methods (metadynamics, umbrella sampling, replica exchange, thermodynamic integration, alchemical), enhanced sampling, coarse-graining, Boltzmann generators, learned samplers, path-integral methods, kinetic Monte Carlo applied to dynamics. Includes biomolecular MD if it's an atomistic-simulation methods paper.
- "DFT & Quantum Chemistry": density functional theory, exchange-correlation functionals, GW/BSE, post-Hartree-Fock methods (CCSD, MP2), embedding theories, DMFT, semi-empirical/tight-binding, automated DFT workflows, papers using/improving codes like VASP, CP2K, Quantum ESPRESSO, ORCA, Psi4, GPAW.
- "Materials Discovery & Generative Models": crystal structure prediction, generative models for crystals/molecules, high-throughput screening for materials, active learning / Bayesian optimization for materials, property prediction for materials, defect/surface/adsorption studies, batteries, catalysts, MOFs, perovskites — when the focus is on discovery or property prediction rather than methods.
- "Methods & Theory": equivariant neural networks, diffusion / flow-matching / normalizing flows applied to atomistic systems, geometric deep learning theory, energy-based models, theoretical statistical mechanics, anything that's a methods/theory contribution that doesn't cleanly fit the other buckets.

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

        # Fallback: all unclassified -> caught by Methods & Theory in caller
        return ["Methods & Theory"] * len(papers)

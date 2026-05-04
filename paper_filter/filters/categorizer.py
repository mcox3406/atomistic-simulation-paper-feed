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

        prompt = f"""Categorize each paper into exactly one of these research areas. Every paper has already passed a strict atomistic-simulation relevance filter, so all five buckets assume that context.

{categories_list}

Papers to categorize:
{papers_text}

Guidelines:
- "MLIPs & Foundation Models": machine-learned interatomic potentials, neural-network potentials, equivariant GNNs trained on energies/forces, universal / foundation potentials (NequIP, MACE, Allegro, SchNet, GemNet, PaiNN, MatterSim, UMA, eSEN, Orb, GNoME, ANI, AIMNet, etc.); training-data strategies, fine-tuning, transferability studies, benchmarks of ML potentials, downstream applications driven primarily by an MLIP.
- "Molecular Dynamics & Sampling": classical or ab initio MD, free-energy methods (metadynamics, umbrella sampling, replica exchange, thermodynamic integration, alchemical), enhanced sampling, coarse-graining, Boltzmann generators / learned samplers tied to a potential, path-integral MD, kinetic Monte Carlo applied to dynamics. Use this bucket when the central methodology is the simulation/sampling technique itself, not the potential.
- "DFT & Quantum Chemistry": density functional theory and exchange-correlation development, GW/BSE, post-Hartree-Fock methods (CCSD, MP2), embedding theories (QM/MM, DMFT), semi-empirical / tight-binding (DFTB, GFN-xTB), automated DFT workflows, methodological papers around codes like VASP, CP2K, Quantum ESPRESSO, ORCA, Psi4, GPAW. Use this when the focus is the electronic-structure method, not its downstream application.
- "Materials Discovery & Generative Models": crystal structure prediction; polymorph search; generative models that produce 3D atomic configurations of crystals/molecules; high-throughput DFT/MLIP screening; active learning / Bayesian optimization driving atomistic calculations; defect / surface / adsorption studies; batteries, catalysts, MOFs, perovskites — when the focus is discovery or property prediction via atomistic simulation rather than the simulation method itself.
- "Methods & Theory": atomistic-simulation methods or theory that don't fit cleanly above — e.g. equivariant / geometric architectures whose contribution is the architecture itself but with atomistic validation; new flow-matching or diffusion frameworks for 3D atomic systems; statistical-mechanics theory for simulated ensembles; uncertainty quantification frameworks for atomistic ML. This is NOT a generic-ML catch-all; if the paper isn't atomistic, it shouldn't have made it this far.

Pick the best single bucket per paper. When two fit, prefer the one that names the dominant technical contribution.

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

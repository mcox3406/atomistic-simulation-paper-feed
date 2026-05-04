# Atomistic Simulation Paper Feed

Daily feed of papers in computational chemistry, materials science, and atomistic machine learning. Fetches from arXiv, bioRxiv, ChemRxiv, major journals (Nature/Science families, JCTC, JCIM, JACS, ACS Catalysis, Digital Discovery, Chem. Sci., PCCP, Angew., Chem, npj Comp. Mat., Patterns), and OpenReview workshops. First-pass keyword filter, then Claude scores each candidate for relevance to the configured domain. Hits get posted to a Slack channel and written to a static JSON file that the web frontend reads.

Adapted from [`lab-paper-digest`](https://github.com/connorcoley/lab-paper-digest), with the same fetch/filter pipeline but no voting/comments backend.

## Architecture

```
GitHub Actions (cron)
  └── python run.py
        ├── Fetch from arXiv / bioRxiv / ChemRxiv / journal RSS / OpenReview
        ├── Keyword filter
        ├── Claude relevance scoring + categorization
        ├── Post to Slack
        └── Write frontend/public/data/papers/<date>.json + index.json
              └── git commit + push
                    └── Cloudflare Pages (or any static host) rebuilds frontend
```

No database, no auth. The frontend just fetches the committed JSON.

## Setup

**1. GitHub secrets** (Settings → Secrets and variables → Actions):
- `ANTHROPIC_API_KEY`
- `SLACK_WEBHOOK_URL`. Slack incoming webhook URL for the channel you want papers posted in.
- `OPENREVIEW_USERNAME` and `OPENREVIEW_PASSWORD`. Credentials for a free account at [openreview.net](https://openreview.net).

**2. Edit `config.json`** to taste:
- `lab_description` is what Claude reads when scoring. Rewrite to match your domain.
- `keywords` is the first-pass filter (cheap, broad). The LLM does NOT see this list.
- `relevance_threshold` is the LLM score cutoff. Default is 0.75.
- `min_impact_factor` drops journals below that impact factor. Preprints always pass.
- `sources.arxiv_categories` and `sources.openreview_workshops` opt sources in or out.
- `sources.journals` is documentation only. The actual journal RSS list lives in `paper_filter/fetchers/journals.py`.

**3. Edit `key_authors.json`** if you want certain authors to bypass the LLM filter and get bolded everywhere.

**4. Run the workflow**: Actions → "Daily Paper Feed" → Run workflow.

## Local development

```bash
pip install -r requirements.txt
cp .env.example .env  # set ANTHROPIC_API_KEY, SLACK_WEBHOOK_URL (or use --dry-run)
python run.py --dry-run --test     # 50-paper smoke test, no Slack post
python run.py --sync-history       # mark currently fetchable papers as seen, no LLM
```

Frontend:

```bash
cd frontend
npm install
npm run dev    # vite dev server, reads frontend/public/data/papers/
```

The first run will write `frontend/public/data/papers/<today>.json` and refresh `index.json`. Until then the page shows an empty state.

## Categories

Papers are sorted into one of:

- **MLIPs & Foundation Models** covers development, training data, benchmarks, transferability, and fine-tuning of machine-learned interatomic potentials (NequIP, MACE, Allegro, MatterSim, UMA, Orb, eSEN, GNoME, etc.). Application papers that just use an MLIP go elsewhere.
- **Molecular Dynamics & Sampling** covers classical and ab initio MD, free-energy methods, enhanced sampling, coarse-graining, learned samplers, path-integral MD, and kinetic Monte Carlo.
- **Electronic Structure** covers DFT and exchange-correlation development, GW/BSE, post-Hartree-Fock methods, embedding theories, semi-empirical and tight-binding methods, and automated DFT workflows.
- **Generative & Geometric ML for Atoms** covers generative models for 3D atomic systems (diffusion, flow matching, autoregressive crystal/molecule generation) and equivariant or geometric architectures whose contribution is the model itself.
- **Materials Discovery & High-Throughput** covers crystal structure prediction, polymorph search, high-throughput DFT/MLIP screening, and active-learning or Bayesian-optimization campaigns. The contribution is the search itself, prioritizing breadth.
- **Atomistic Applications** covers mechanistic and property studies of specific systems like catalysis, batteries, defects, surfaces, MOFs, perovskites, and 2D materials. The contribution is understanding a specific material or process in depth.

The category list lives in `paper_filter/filters/categorizer.py` (Python prompt) and `frontend/src/App.jsx` (UI). Keep them in sync.

## Hosting (GitHub Pages)

Site lives at `https://<user>.github.io/atomistic-simulation-paper-feed/`. One-time setup:

1. Repo Settings → Pages → **Source: GitHub Actions**.
2. Push to `main`. The `Deploy Pages` workflow builds `frontend/` and publishes.

After that, the deploy workflow re-runs in two cases:
- A push to `main` that touches `frontend/` (or the deploy workflow itself) triggers a deploy.
- A successful run of `Daily Paper Feed` triggers a redeploy via `workflow_run`, so new papers show up on the site without manual intervention.

If you want a custom domain or root path later, you'll need to drop `base` in `frontend/vite.config.js` (or change it to match the new path) and re-deploy.

## Schedule

Cron in `.github/workflows/daily-feed.yml` runs at 12:00 UTC (8am EDT). Edit there to change.

## Layout

```
config.json              # domain description, keywords, sources, threshold
key_authors.json         # bypass-the-LLM list
posted_papers.json       # dedup history, committed by Actions
run.py                   # CLI entry point
paper_filter/
  fetchers/              # arxiv, biorxiv, chemrxiv, journals, openreview
  filters/               # keyword + LLM scoring + categorization
  slack.py               # Slack webhook posting
  json_export.py         # writes data files for the frontend
  pipeline.py            # orchestration
frontend/
  src/                   # React app
  public/data/papers/    # JSON written by the pipeline (committed)
  vite.config.js
.github/workflows/daily-feed.yml
```

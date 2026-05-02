# Atomistic Simulation Paper Feed

Daily feed of papers in computational chemistry, materials science, and atomistic machine learning. Fetches from arXiv, bioRxiv, ChemRxiv, major journals (Nature/Science families, JCTC, JCIM, JACS, ACS Catalysis, Digital Discovery, Chem. Sci., PCCP, Angew., Chem, npj Comp. Mat., Patterns), and OpenReview workshops. First-pass keyword filter, then Claude scores each candidate for relevance to the configured domain. Hits get posted to a Slack channel and written to a static JSON file that the web frontend reads.

Adapted from [`lab-paper-digest`](https://github.com/connorcoley/lab-paper-digest) — same fetch/filter pipeline, no voting/comments backend.

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
- `SLACK_WEBHOOK_URL` — Slack incoming webhook for the channel you want papers in
- `OPENREVIEW_USERNAME`, `OPENREVIEW_PASSWORD` — free account at [openreview.net](https://openreview.net)

**2. Edit `config.json`** to taste:
- `lab_description` — used by Claude when scoring; describe the domain you want
- `keywords` — first-pass filter (cheap, broad). LLM does NOT see this list
- `relevance_threshold` — score cutoff (default 0.6)
- `min_impact_factor` — drops journals below this IF; preprints always pass
- `sources.arxiv_categories`, `sources.openreview_workshops` — opt in/out
- `sources.journals` — documentation only; the actual journal RSS list lives in `paper_filter/fetchers/journals.py`

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

- **MLIPs & Foundation Models** — NequIP, MACE, Allegro, MatterSim, UMA, Orb, eSEN, GNoME, …
- **Molecular Dynamics & Sampling** — classical/AIMD, free energy, enhanced sampling, coarse-graining, Boltzmann generators
- **DFT & Quantum Chemistry** — functionals, GW/BSE, post-HF, embedding, automated DFT
- **Materials Discovery & Generative Models** — CSP, screening, BO/active learning for materials, generative models for crystals/molecules
- **Methods & Theory** — equivariance, diffusion / flow matching for atomistic systems, geometric deep learning theory, anything else

The category list lives in `paper_filter/filters/categorizer.py` (Python prompt) and `frontend/src/App.jsx` (UI). Keep them in sync.

## Hosting (GitHub Pages)

Site lives at `https://<user>.github.io/atomistic-simulation-paper-feed/`. One-time setup:

1. Repo Settings → Pages → **Source: GitHub Actions**.
2. Push to `main`. The `Deploy Pages` workflow builds `frontend/` and publishes.

After that, the deploy workflow re-runs in two cases:
- **Frontend changes pushed to `main`** — only when files under `frontend/` (or the workflow itself) change.
- **Daily Paper Feed completes** — `workflow_run` triggers a redeploy so new papers show up on the site without you doing anything.

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

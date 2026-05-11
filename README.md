# Atomistic Simulation Paper Feed

A daily feed of papers in computational chemistry, materials science, and atomistic ML. Sources include arXiv, bioRxiv, ChemRxiv, OpenReview workshops, and journal RSS feeds across Nature, Science, ACS (JCTC, JCIM), RSC (Digital Discovery, Chem. Sci., Chem. Commun., PCCP), APS (PRB, PR Materials), AIP (J. Chem. Phys.), Wiley (Angew., J. Comp. Chem., WIREs CMS), Cell Press (Chem), Elsevier (Acta Materialia, Comp. Mat. Sci.), and IOP (Modelling Simul. Mater. Sci. Eng.). A simple keyword pre-filter trims the volume, and an LLM (DeepSeek V4 Flash by default; Claude Haiku still supported via `"provider": "anthropic"` in `config.json`) then scores each candidate for relevance and assigns it to one of six buckets. Hits are posted to Slack and committed as JSON for the static site.

Live at **[mcox3406.github.io/atomistic-simulation-paper-feed](https://mcox3406.github.io/atomistic-simulation-paper-feed/)**.

![screenshot](assets/website.png)

Adapted from [`lab-paper-feed`](https://github.com/mcox3406/lab-paper-feed).

> [!NOTE]
> **ChemRxiv is fetched via Crossref.** The native ChemRxiv API has been Cloudflare-gated since the 2026-01-21 migration to Wiley's Research Exchange Preprints platform, so headless clients get HTTP 403. We route through Crossref's Works API by DOI prefix (`10.26434`) instead. Crossref doesn't carry ChemRxiv abstracts, so titles are scored alone (the LLM is told to be lenient for these).

## Setup

1. Add GitHub Actions secrets: `DEEPSEEK_API_KEY` (for the default provider), `SLACK_WEBHOOK_URL`, `OPENREVIEW_USERNAME`, `OPENREVIEW_PASSWORD`. Add `ANTHROPIC_API_KEY` only if you set `"provider": "anthropic"` in `config.json`.
2. Edit `config.json`. The important knobs are `lab_description` (what the scorer matches against), `keywords` (cheap pre-filter, never seen by the LLM), `relevance_threshold`, `min_impact_factor`, and `provider` (`deepseek` or `anthropic`).
3. Edit `key_authors.json` to flag authors who should bypass the LLM filter.
4. Trigger the **Daily Paper Feed** workflow manually once, or wait for the 12:00 UTC cron.
5. For the site: Settings -> Pages -> Source: GitHub Actions. The deploy workflow rebuilds on every successful feed run.

If you forked this repo, `posted_papers.json` carries my existing dedup history (papers already shown here). Reset it before your first run so you don't miss recent papers: `echo '{}' > posted_papers.json`, or run `python run.py --sync-history` to mark currently fetchable papers as seen and start fresh from there.

## Local dev

Set up a virtualenv, install deps, and run the pipeline against a small slice without posting to Slack:

```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env   # fill in keys
uv run python run.py --dry-run --test   # 50-paper smoke test, no Slack
uv run python run.py --sync-history     # mark currently fetchable papers as seen, no LLM
```

For the frontend, install Node deps and start the Vite dev server (it reads whatever JSON is already in `frontend/public/data/papers/`):

```bash
cd frontend && npm install && npm run dev
```

## Contributing

PRs welcome and very much appreciated. Some easy ways to help:

- **Key authors** (`key_authors.json`): add anyone whose papers should always surface.
- **Fetchers** (`paper_filter/fetchers/`): add a new source or fix a flaky feed.
- **Styling** (`frontend/src/App.jsx`): the UI is plain inline-style React, easy to tweak.
- **Categorizer prompt** (`paper_filter/filters/categorizer.py`): if a category is mis-bucketing, tighten the prompt.

If you change the category list, update both `paper_filter/filters/categorizer.py` and `frontend/src/App.jsx` so they stay in sync.

## Layout

```
config.json              domain description, keywords, sources, threshold
key_authors.json         bypass-the-LLM list
posted_papers.json       dedup history (committed by Actions)
run.py                   CLI entry point
paper_filter/
  fetchers/              arxiv, biorxiv, chemrxiv, journals, openreview
  filters/               keyword + LLM scoring + categorization
  slack.py               webhook posting
  json_export.py         writes data files for the frontend
  pipeline.py            orchestration
frontend/
  src/                   React app
  public/data/papers/    JSON written by the pipeline (committed)
.github/workflows/       daily-feed.yml, deploy-pages.yml
```

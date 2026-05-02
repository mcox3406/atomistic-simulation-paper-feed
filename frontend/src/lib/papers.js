// Static-JSON data layer. Files live under /data/papers/ (served from public/).
// index.json is a list of {date, count}, newest first.
// <YYYY-MM-DD>.json is the array of papers added on that date.

const BASE = `${import.meta.env.BASE_URL || '/'}data/papers`

async function fetchJson(path) {
  const res = await fetch(path, { cache: 'no-cache' })
  if (!res.ok) throw new Error(`Fetch failed: ${path} (${res.status})`)
  return res.json()
}

export async function fetchAvailableDates() {
  try {
    return await fetchJson(`${BASE}/index.json`)
  } catch (err) {
    // Empty repo / first run before any data is committed
    console.warn('No paper index yet:', err.message)
    return []
  }
}

export async function fetchPapersForDate(date) {
  const papers = await fetchJson(`${BASE}/${date}.json`)
  return papers.sort((a, b) => (b.relevance_score || 0) - (a.relevance_score || 0))
}

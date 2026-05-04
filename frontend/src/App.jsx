import React, { useState, useMemo, useEffect } from 'react'
import { fetchAvailableDates, fetchPapersForDate } from './lib/papers'

const CATEGORIES = [
  "All",
  "MLIPs & Foundation Models",
  "Molecular Dynamics & Sampling",
  "Electronic Structure",
  "Generative & Geometric ML for Atoms",
  "Materials Discovery & High-Throughput",
  "Atomistic Applications",
]

const CATEGORY_COLORS = {
  "MLIPs & Foundation Models": "#2563eb",
  "Molecular Dynamics & Sampling": "#7c3aed",
  "Electronic Structure": "#059669",
  "Generative & Geometric ML for Atoms": "#db2777",
  "Materials Discovery & High-Throughput": "#d97706",
  "Atomistic Applications": "#475569",
}

const CATEGORY_SHORT = {
  "MLIPs & Foundation Models": "MLIPs",
  "Molecular Dynamics & Sampling": "MD & Sampling",
  "Electronic Structure": "Electronic Structure",
  "Generative & Geometric ML for Atoms": "Generative ML",
  "Materials Discovery & High-Throughput": "Discovery & HT",
  "Atomistic Applications": "Applications",
}

const CATEGORY_DESCRIPTIONS = {
  "MLIPs & Foundation Models": "Development, training data, benchmarks, transferability, and fine-tuning of machine-learned interatomic potentials. Application papers that just use an MLIP go elsewhere. This bucket is about the potential itself.",
  "Molecular Dynamics & Sampling": "Classical and ab initio MD, free-energy methods, enhanced sampling, coarse-graining, learned samplers, path-integral MD, kinetic Monte Carlo. Also statistical-mechanics theory for simulated ensembles.",
  "Electronic Structure": "DFT and exchange-correlation development, GW/BSE, post-Hartree-Fock methods, embedding theories, semi-empirical / tight-binding, automated DFT workflows, methodological work tied to electronic-structure codes (VASP, CP2K, ORCA, etc.).",
  "Generative & Geometric ML for Atoms": "Generative models for 3D atomic systems (diffusion, flow matching, autoregressive crystal/molecule generation) and equivariant / geometric architectures whose contribution is the model itself.",
  "Materials Discovery & High-Throughput": "Crystal structure prediction, polymorph search, high-throughput DFT/MLIP screening, active learning and Bayesian optimization campaigns. The contribution is the search itself, prioritizing breadth over depth.",
  "Atomistic Applications": "Mechanistic and property studies of specific systems like catalysis, batteries, defects, surfaces, MOFs, perovskites, and 2D materials. The contribution is understanding a specific material or process in depth.",
}

// Journals that often ship empty/garbled abstracts in their RSS feeds.
const JOURNALS_WITH_ABSTRACT_ISSUES = new Set([
  'JACS', 'JCIM', 'JCTC', 'ACS Central Science', 'ACS Catalysis',
  'Digital Discovery', 'Chemical Science', 'Chem. Commun.', 'PCCP',
])

function isAbstractMissing(abstract) {
  if (!abstract || abstract.trim() === '') return true
  if (abstract.trim().startsWith('<') || abstract.includes('<img')) return true
  return false
}

// Bold key authors and truncate long lists, keeping first N-1, last,
// and any key authors that would otherwise be hidden.
function formatAuthors(authors, keyAuthors = [], maxAuthors = 10) {
  if (!authors || authors.length === 0) return null

  const keyAuthorSet = new Set((keyAuthors || []).map(a => a.toLowerCase()))
  const isKey = (name) => keyAuthorSet.has(name.toLowerCase())
  const fmt = (name, i) => isKey(name)
    ? <strong key={i} style={{ fontWeight: 600 }}>{name}</strong>
    : <span key={i}>{name}</span>

  if (authors.length <= maxAuthors) {
    return authors.map((a, i) => (
      <span key={i}>{fmt(a, i)}{i < authors.length - 1 ? ', ' : ''}</span>
    ))
  }

  const shown = new Set()
  for (let i = 0; i < maxAuthors - 1; i++) shown.add(i)
  shown.add(authors.length - 1)
  authors.forEach((a, i) => { if (isKey(a)) shown.add(i) })

  const sorted = Array.from(shown).sort((a, b) => a - b)
  const parts = []
  let prev = -1
  sorted.forEach((idx, i) => {
    if (prev >= 0 && idx > prev + 1) parts.push(<span key={`ellipsis-${idx}`}>...</span>)
    parts.push(fmt(authors[idx], idx))
    if (i < sorted.length - 1) parts.push(<span key={`comma-${idx}`}>, </span>)
    prev = idx
  })
  return parts
}

function PaperCard({ paper, expanded, onToggleExpand }) {
  const sourceColors = {
    'arxiv': '#b31b1b',
    'biorxiv': '#782a2a',
    'chemrxiv': '#3b5998',
    'openreview': '#1f6feb',
  }
  const sourceColor = sourceColors[paper.source?.toLowerCase()] || '#374151'

  return (
    <div style={{
      background: '#fff',
      borderRadius: '12px',
      padding: '24px',
      marginBottom: '16px',
      boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 4px 12px rgba(0,0,0,0.04)',
      border: '1px solid #e5e7eb',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{
            background: sourceColor,
            color: '#fff',
            padding: '3px 10px',
            borderRadius: '4px',
            fontSize: '11px',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.5px'
          }}>
            {paper.source}
          </span>
          <span style={{
            background: (CATEGORY_COLORS[paper.category] || '#64748b') + '15',
            color: CATEGORY_COLORS[paper.category] || '#64748b',
            padding: '3px 10px',
            borderRadius: '4px',
            fontSize: '11px',
            fontWeight: 600
          }}>
            {CATEGORY_SHORT[paper.category] || paper.category}
          </span>
          <span style={{ color: '#6b7280', fontSize: '12px' }}>
            {paper.published || paper.added_date}
          </span>
        </div>
        <div style={{
          background: `linear-gradient(135deg, ${paper.relevance_score > 0.85 ? '#10b981' : paper.relevance_score > 0.7 ? '#f59e0b' : '#6b7280'} 0%, ${paper.relevance_score > 0.85 ? '#059669' : paper.relevance_score > 0.7 ? '#d97706' : '#4b5563'} 100%)`,
          color: '#fff',
          padding: '4px 10px',
          borderRadius: '20px',
          fontSize: '12px',
          fontWeight: 600
        }}>
          {(paper.relevance_score * 100).toFixed(0)}% match
        </div>
      </div>

      <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: 600, lineHeight: 1.4, color: '#111827' }}>
        <a href={paper.url} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'none' }}>
          {paper.title}{paper.version != null ? ` (v${paper.version})` : ''}
        </a>
        {paper.pdf_url && (
          <a href={paper.pdf_url} target="_blank" rel="noopener noreferrer" style={{
            marginLeft: '8px', fontSize: '13px', color: '#2563eb', fontWeight: 500
          }}>
            [pdf]
          </a>
        )}
      </h3>

      <p style={{ margin: '0 0 12px 0', fontSize: '14px', color: '#6b7280' }}>
        {formatAuthors(paper.authors, paper.key_authors, 10)}
      </p>

      {isAbstractMissing(paper.abstract) && JOURNALS_WITH_ABSTRACT_ISSUES.has(paper.source) ? (
        <p style={{ margin: '0 0 16px 0', fontSize: '14px', lineHeight: 1.6, color: '#94a3b8', fontStyle: 'italic' }}>
          Abstract not available via RSS feed. Click the title to view on the publisher site.
        </p>
      ) : (
        <p style={{
          margin: '0 0 16px 0',
          fontSize: '14px',
          lineHeight: 1.6,
          color: '#374151',
          overflow: 'hidden',
          display: '-webkit-box',
          WebkitLineClamp: expanded ? 'none' : 3,
          WebkitBoxOrient: 'vertical'
        }}>
          {paper.abstract}
        </p>
      )}

      {!expanded && paper.abstract?.length > 200 && !isAbstractMissing(paper.abstract) && (
        <button onClick={onToggleExpand} style={{
          background: 'none', border: 'none', color: '#2563eb',
          fontSize: '13px', cursor: 'pointer', padding: 0, marginBottom: '16px', fontWeight: 500
        }}>
          Show more
        </button>
      )}
      {expanded && (
        <button onClick={onToggleExpand} style={{
          background: 'none', border: 'none', color: '#2563eb',
          fontSize: '13px', cursor: 'pointer', padding: 0, marginBottom: '16px', fontWeight: 500
        }}>
          Show less
        </button>
      )}

      {paper.relevance_reason && (
        <div style={{
          background: '#f8fafc',
          borderRadius: '8px',
          padding: '12px 16px',
          borderLeft: '3px solid #2563eb'
        }}>
          <span style={{ fontSize: '12px', color: '#64748b', fontWeight: 500 }}>Why this paper: </span>
          <span style={{ fontSize: '13px', color: '#334155' }}>{paper.relevance_reason}</span>
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [selectedCategory, setSelectedCategory] = useState("All")
  const [selectedDate, setSelectedDate] = useState(null)
  const [expandedPapers, setExpandedPapers] = useState(new Set())
  const [sortBy, setSortBy] = useState('relevance')

  const [papers, setPapers] = useState([])
  const [availableDates, setAvailableDates] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function loadDates() {
      try {
        const dates = await fetchAvailableDates()
        if (cancelled) return
        setAvailableDates(dates)
        if (dates.length > 0) setSelectedDate(dates[0].date)
        else setLoading(false)
      } catch (err) {
        if (!cancelled) {
          console.error(err)
          setError('Failed to load index.')
          setLoading(false)
        }
      }
    }
    loadDates()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!selectedDate) return
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchPapersForDate(selectedDate)
      .then((data) => { if (!cancelled) setPapers(data) })
      .catch((err) => {
        console.error(err)
        if (!cancelled) setError(`Failed to load papers for ${selectedDate}.`)
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [selectedDate])

  const filteredPapers = useMemo(() => {
    let result = papers
    if (selectedCategory !== "All") result = result.filter(p => p.category === selectedCategory)
    if (sortBy === 'relevance') {
      result = [...result].sort((a, b) => (b.relevance_score || 0) - (a.relevance_score || 0))
    } else if (sortBy === 'newest') {
      result = [...result].sort((a, b) => new Date(b.published || b.added_date) - new Date(a.published || a.added_date))
    }
    return result
  }, [papers, selectedCategory, sortBy])

  const categoryCounts = useMemo(() => {
    const counts = { All: papers.length }
    CATEGORIES.slice(1).forEach(cat => {
      counts[cat] = papers.filter(p => p.category === cat).length
    })
    return counts
  }, [papers])

  const toggleExpand = (paperId) => {
    setExpandedPapers(prev => {
      const next = new Set(prev)
      if (next.has(paperId)) next.delete(paperId)
      else next.add(paperId)
      return next
    })
  }

  const formatDate = (dateStr) => {
    const date = new Date(dateStr + 'T00:00:00')
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)
    if (date.getTime() === today.getTime()) return 'Today'
    if (date.getTime() === yesterday.getTime()) return 'Yesterday'
    return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%)',
      fontFamily: "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif"
    }}>
      <header style={{
        background: '#fff',
        borderBottom: '1px solid #e2e8f0',
        padding: '20px 0',
        position: 'sticky',
        top: 0,
        zIndex: 100,
        boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
      }}>
        <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '0 24px' }}>
          <div style={{ marginBottom: '16px' }}>
            <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 700, color: '#0f172a', letterSpacing: '-0.5px' }}>
              Atomistic Simulation Paper Feed
            </h1>
            <p style={{ margin: '4px 0 0 0', fontSize: '14px', color: '#64748b' }}>
              Daily papers in computational chemistry and materials science, scored by Claude.
            </p>
          </div>

          {availableDates.length > 0 && (
            <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', overflowX: 'auto' }}>
              {availableDates.slice(0, 7).map(({ date, count }) => (
                <button
                  key={date}
                  onClick={() => setSelectedDate(date)}
                  style={{
                    background: selectedDate === date ? '#2563eb' : '#fff',
                    color: selectedDate === date ? '#fff' : '#475569',
                    border: selectedDate === date ? 'none' : '1px solid #e2e8f0',
                    padding: '8px 16px',
                    borderRadius: '8px',
                    fontWeight: 500,
                    cursor: 'pointer',
                    fontSize: '13px',
                    whiteSpace: 'nowrap'
                  }}
                >
                  {formatDate(date)}
                  <span style={{ marginLeft: '6px', opacity: 0.7, fontSize: '12px' }}>({count})</span>
                </button>
              ))}
            </div>
          )}

          <div style={{ display: 'flex', gap: '6px', overflowX: 'auto', paddingBottom: '4px' }}>
            {CATEGORIES.map(cat => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                style={{
                  background: selectedCategory === cat
                    ? (cat === 'All' ? '#0f172a' : CATEGORY_COLORS[cat])
                    : '#fff',
                  color: selectedCategory === cat ? '#fff' : '#475569',
                  border: selectedCategory === cat ? 'none' : '1px solid #e2e8f0',
                  padding: '8px 14px',
                  borderRadius: '8px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  fontSize: '13px',
                  whiteSpace: 'nowrap',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                {cat === 'All' ? 'All' : CATEGORY_SHORT[cat]}
                <span style={{
                  background: selectedCategory === cat ? 'rgba(255,255,255,0.2)' : '#f1f5f9',
                  padding: '2px 8px',
                  borderRadius: '10px',
                  fontSize: '11px',
                  fontWeight: 600
                }}>
                  {categoryCounts[cat] || 0}
                </span>
              </button>
            ))}
          </div>
        </div>
      </header>

      <main style={{ maxWidth: '1000px', margin: '0 auto', padding: '24px' }}>
        {selectedCategory !== 'All' && CATEGORY_DESCRIPTIONS[selectedCategory] && (
          <div style={{
            background: '#fff',
            borderLeft: `3px solid ${CATEGORY_COLORS[selectedCategory]}`,
            borderRadius: '8px',
            padding: '12px 16px',
            marginBottom: '16px',
            boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
          }}>
            <div style={{
              fontSize: '12px',
              color: CATEGORY_COLORS[selectedCategory],
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
              marginBottom: '4px',
            }}>
              {selectedCategory}
            </div>
            <div style={{ fontSize: '13px', color: '#475569', lineHeight: 1.5 }}>
              {CATEGORY_DESCRIPTIONS[selectedCategory]}
            </div>
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <p style={{ margin: 0, color: '#64748b', fontSize: '14px' }}>
            {loading ? 'Loading...' : `${filteredPapers.length} paper${filteredPapers.length !== 1 ? 's' : ''}`}
            {selectedCategory !== 'All' && ` in ${CATEGORY_SHORT[selectedCategory]}`}
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '13px', color: '#64748b' }}>Sort by:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid #e2e8f0',
                fontSize: '13px',
                color: '#334155',
                cursor: 'pointer',
                background: '#fff'
              }}
            >
              <option value="relevance">Relevance</option>
              <option value="newest">Newest</option>
            </select>
          </div>
        </div>

        {error && (
          <div style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: '8px',
            padding: '16px',
            marginBottom: '20px',
            color: '#991b1b'
          }}>{error}</div>
        )}

        {loading && (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b' }}>
            <div style={{ fontSize: '24px', marginBottom: '16px' }}>Loading papers...</div>
          </div>
        )}

        {!loading && availableDates.length === 0 && (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b' }}>
            <p style={{ fontSize: '16px', margin: 0 }}>
              No papers yet. Run the pipeline to populate <code>frontend/public/data/papers/</code>.
            </p>
          </div>
        )}

        {!loading && availableDates.length > 0 && filteredPapers.length === 0 && (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b' }}>
            <p style={{ fontSize: '16px', margin: 0 }}>
              No papers found for this selection.
            </p>
          </div>
        )}

        {!loading && filteredPapers.map(paper => (
          <PaperCard
            key={paper.id}
            paper={paper}
            expanded={expandedPapers.has(paper.id)}
            onToggleExpand={() => toggleExpand(paper.id)}
          />
        ))}
      </main>

      <footer style={{ textAlign: 'center', padding: '40px 20px', color: '#94a3b8', fontSize: '13px' }}>
        Daily run scored by Claude
      </footer>
    </div>
  )
}

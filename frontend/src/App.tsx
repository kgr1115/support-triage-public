import { useState } from 'react'
import './App.css'
import { SAMPLES } from './samples'
import type { Category, Priority, RetrievedItem, Sentiment, TriageResponse } from './types'

const PRIORITY_LABELS: Record<Priority, string> = {
  urgent: 'Urgent',
  high: 'High',
  normal: 'Normal',
  low: 'Low',
}

const CATEGORY_LABELS: Record<Category, string> = {
  login_issue: 'Login',
  billing_dispute: 'Billing',
  integration_setup: 'Integration',
  feature_request: 'Feature request',
  bug_report: 'Bug report',
}

const SENTIMENT_LABELS: Record<Sentiment, string> = {
  positive: 'Positive',
  neutral: 'Neutral',
  negative: 'Negative',
  frustrated: 'Frustrated',
}

function highlightCitations(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = []
  const pattern = /\[(KB-[A-Z]+-\d+)\]/g
  let lastIndex = 0
  let match: RegExpExecArray | null
  let key = 0
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index))
    }
    parts.push(
      <span className="citation" key={`cite-${key++}`}>
        [{match[1]}]
      </span>,
    )
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex))
  return parts
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score * 100))
  return (
    <div className="score-bar">
      <div className="score-bar-fill" style={{ width: `${pct}%` }} />
      <span className="score-bar-text">{score.toFixed(2)}</span>
    </div>
  )
}

function RetrievalList({
  title,
  items,
  emptyText,
}: {
  title: string
  items: RetrievedItem[]
  emptyText: string
}) {
  return (
    <section className="card">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p className="empty">{emptyText}</p>
      ) : (
        <ul className="retrieved-list">
          {items.map((item) => (
            <li key={item.id}>
              <div className="retrieved-row">
                <code className="kb-id">{item.id}</code>
                <span className="retrieved-title">{item.title}</span>
                <ScoreBar score={item.score} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function App() {
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [draft, setDraft] = useState('')
  const [response, setResponse] = useState<TriageResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function loadSample(idx: number) {
    if (idx < 0 || idx >= SAMPLES.length) return
    setSubject(SAMPLES[idx].subject)
    setBody(SAMPLES[idx].body)
    setResponse(null)
    setError(null)
  }

  async function submit() {
    if (!subject.trim() || !body.trim()) {
      setError('Subject and body are both required.')
      return
    }
    setLoading(true)
    setError(null)
    setResponse(null)
    try {
      const r = await fetch('/triage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject, body }),
      })
      if (!r.ok) {
        const detail = await r.text()
        throw new Error(`HTTP ${r.status}: ${detail}`)
      }
      const data = (await r.json()) as TriageResponse
      setResponse(data)
      setDraft(data.drafted_response.response)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>support-triage</h1>
        <p className="subtitle">
          Local-first AI triage for B2B SaaS support. Classify · retrieve KB · draft a
          citation-grounded reply · suggest macros.
        </p>
      </header>

      <main className="grid">
        <section className="input-pane">
          <div className="card">
            <h3>Ticket</h3>

            <label htmlFor="sample">
              <span className="label-text">Load sample</span>
              <select
                id="sample"
                onChange={(e) => loadSample(Number(e.target.value))}
                defaultValue="-1"
              >
                <option value="-1" disabled>
                  Pick a sample…
                </option>
                {SAMPLES.map((s, i) => (
                  <option key={s.label} value={i}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>

            <label htmlFor="subject">
              <span className="label-text">Subject</span>
              <input
                id="subject"
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="One-line ticket subject"
                maxLength={200}
              />
            </label>

            <label htmlFor="body">
              <span className="label-text">Body</span>
              <textarea
                id="body"
                rows={10}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Customer's full message"
              />
            </label>

            <button onClick={submit} disabled={loading} className="primary">
              {loading ? 'Triaging…' : 'Triage'}
            </button>

            {error && <div className="error">{error}</div>}
          </div>
        </section>

        <section className="result-pane">
          {!response && !loading && !error && (
            <div className="card placeholder">
              <p>Submit a ticket to see the agent view.</p>
            </div>
          )}

          {response && (
            <>
              <section className="card">
                <h3>Classification</h3>
                <div className="badges">
                  <span className={`badge priority-${response.classification.priority}`}>
                    {PRIORITY_LABELS[response.classification.priority]}
                  </span>
                  <span className="badge category">
                    {CATEGORY_LABELS[response.classification.category]}
                  </span>
                  <span className={`badge sentiment-${response.classification.sentiment}`}>
                    {SENTIMENT_LABELS[response.classification.sentiment]}
                  </span>
                </div>
              </section>

              <RetrievalList
                title="Retrieved KB articles"
                items={response.retrieved_kb}
                emptyText="No KB matches."
              />

              <section className="card">
                <h3>Drafted response</h3>
                <p className="hint">
                  Editable. Citations link claims back to the KB articles above.
                </p>
                <div className="draft-preview">{highlightCitations(draft)}</div>
                <textarea
                  className="draft-editor"
                  rows={10}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                />
                {response.drafted_response.cited_kb_ids.length > 0 && (
                  <p className="cited">
                    <span className="label-text">Cited:</span>{' '}
                    {response.drafted_response.cited_kb_ids.map((id) => (
                      <code key={id} className="kb-id">
                        {id}
                      </code>
                    ))}
                  </p>
                )}
              </section>

              <RetrievalList
                title="Suggested macros (top 3)"
                items={response.suggested_macros}
                emptyText="No macro matches."
              />
            </>
          )}
        </section>
      </main>
    </div>
  )
}

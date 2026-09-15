/**
 * RightPanel — Artifacts, Sources, and Model controls
 *
 * ArtifactTab security notes:
 *   - HTML artifacts are rendered in a sandboxed <iframe> with sandbox=""
 *     (the empty string is the strictest mode: blocks scripts, popups, form
 *     submission, same-origin access, and top-navigation).
 *   - allow-scripts is intentionally NOT added — all generated HTML is
 *     treated as untrusted content.
 *   - CSP-equivalent constraint is enforced via the sandbox attribute itself.
 *   - Markdown artifacts are rendered via react-markdown (no eval/innerHTML).
 */

import { useState, useEffect } from 'react'
import Markdown from 'react-markdown'

const TABS = ['Artifact', 'Sources', 'Model']
const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// --------------------------------------------------------------------------
// Artifact Tab
// --------------------------------------------------------------------------
function ArtifactTab({ artifact }) {
  const [viewRaw, setViewRaw] = useState(false)

  // Reset raw toggle whenever the artifact changes (e.g. session switch)
  useEffect(() => { setViewRaw(false) }, [artifact])

  if (!artifact) {
    return (
      <div>
        <div className="placeholder-card">
          <div className="card-label">Generated artifact</div>
          <div className="card-content">
            <div className="placeholder-line long" />
            <div className="placeholder-line medium" />
            <div className="placeholder-line long" />
            <div className="placeholder-line short" />
          </div>
        </div>
        <p className="text-muted" style={{ fontSize: '12px', marginTop: '8px' }}>
          Artifacts will appear here after the assistant generates a Ship&nbsp;30 essay,
          an HTML dashboard, or a one-pager.
        </p>
      </div>
    )
  }

  const isHtml = artifact.type === 'html'

  const handleCopy = () => {
    navigator.clipboard.writeText(artifact.content)
      .then(() => alert('Copied to clipboard!'))
      .catch(() => alert('Copy failed — please select the text manually.'))
  }

  const handleDownload = () => {
    const ext = isHtml ? 'html' : 'md'
    const mime = isHtml ? 'text/html' : 'text/markdown'
    const blob = new Blob([artifact.content], { type: mime })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `growth_room_artifact.${ext}`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="artifact-container">
      {/* Header: badge + actions */}
      <div className="artifact-header">
        <span className={`artifact-badge artifact-badge-${artifact.type}`}>
          {artifact.type.toUpperCase()}
        </span>
        <div className="artifact-actions">
          {/* Toggle available for both HTML and Markdown */}
          <button
            id="btn-artifact-toggle"
            className="btn-minimal"
            onClick={() => setViewRaw(r => !r)}
            title={viewRaw ? 'Show rendered view' : 'Show raw source'}
          >
            {viewRaw ? '👁 Rendered' : '</> Source'}
          </button>
          <button className="btn-minimal" onClick={handleCopy} title="Copy to clipboard">
            📋 Copy
          </button>
          <button className="btn-minimal" onClick={handleDownload} title="Download file">
            ⬇ Download
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="artifact-body">
        {viewRaw ? (
          /* Raw source view — shown for both HTML and Markdown */
          <pre className="code-block">
            <code>{artifact.content}</code>
          </pre>
        ) : isHtml ? (
          /*
           * Sandboxed iframe — security notes:
           *   - sandbox="" (empty) is the strictest level: no scripts, no
           *     same-origin access, no form submission, no popups.
           *   - allow-scripts is deliberately omitted.
           *   - srcDoc avoids any HTTP request for the content.
           */
          <div className="iframe-wrapper">
            <iframe
              id="artifact-iframe"
              title="Rendered HTML artifact"
              srcDoc={artifact.content}
              sandbox=""
              style={{
                width: '100%',
                height: '460px',
                border: 'none',
                background: '#fff',
                display: 'block',
              }}
            />
          </div>
        ) : (
          /* Markdown rendered view */
          <div className="markdown-artifact">
            <Markdown>{artifact.content}</Markdown>
          </div>
        )}
      </div>
    </div>
  )
}

// --------------------------------------------------------------------------
// Sources Tab
// --------------------------------------------------------------------------
function SourcesTab({ sources }) {
  if (!sources || sources.length === 0) {
    return (
      <p className="text-muted" style={{ fontSize: '12px' }}>
        No sources retrieved for current context.
      </p>
    )
  }

  return (
    <div>
      <p className="text-muted" style={{ fontSize: '11px', marginBottom: '12px' }}>
        {sources.length} source{sources.length !== 1 ? 's' : ''} cited
      </p>
      {sources.map((s, idx) => (
        <div key={idx} className="source-chip">
          <div className="source-episode">
            <span className="source-index">[{idx + 1}]</span> {s.episode_title}
          </div>
          {s.guest && (
            <div className="source-guest">{s.guest}</div>
          )}
          <div className="source-meta">
            {s.segment_timestamp && <span>{s.segment_timestamp} · </span>}
            {s.relevance_score != null && (
              <span>Score: {s.relevance_score.toFixed(3)}</span>
            )}
          </div>
          {s.source_url && (
            <a
              href={s.source_url}
              target="_blank"
              rel="noreferrer noopener"
              className="source-link"
            >
              Watch on YouTube ↗
            </a>
          )}
        </div>
      ))}
    </div>
  )
}

// --------------------------------------------------------------------------
// Model Tab
// --------------------------------------------------------------------------
function ModelTab() {
  const [statusData, setStatusData] = useState(null)
  const [loading, setLoading] = useState(false)

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API}/model/status`)
      const json = await res.json()
      setStatusData(json.data)
    } catch (e) {
      console.error('Model status fetch failed:', e)
    }
  }

  useEffect(() => { fetchStatus() }, [])

  const handleProviderSwitch = async (e) => {
    setLoading(true)
    const provider = e.target.value
    try {
      await fetch(`${API}/model/select`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider }),
      })
      await fetchStatus()
    } catch (err) {
      console.error('Provider switch failed:', err)
    } finally {
      setLoading(false)
    }
  }

  if (!statusData) {
    return <div className="text-muted">Loading model status…</div>
  }

  let pillClass = 'status-green'
  let pillText = 'Connected'
  if (statusData.fallback_active) {
    pillClass = 'status-yellow'
    pillText = 'Fallback Active'
  }

  return (
    <div>
      <div className="placeholder-card">
        <div className="card-header-row">
          <div className="card-label">Provider Status</div>
          <div className={`status-pill ${pillClass}`}>{pillText}</div>
        </div>
        <table className="model-table">
          <tbody>
            <tr>
              <td>Configured</td>
              <td>{statusData.configured_provider}</td>
            </tr>
            <tr>
              <td>Active</td>
              <td style={{ fontWeight: 'bold' }}>{statusData.active_provider}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="placeholder-card" style={{ marginTop: '16px' }}>
        <div className="card-label">Provider Override</div>
        <div className="radio-group" style={{ marginTop: '8px' }}>
          <label>
            <input
              type="radio" value="auto" name="provider"
              disabled={loading}
              checked={!['anthropic', 'ollama'].includes(statusData.configured_provider)}
              onChange={handleProviderSwitch}
            />
            Auto (env default)
          </label>
          <label>
            <input
              type="radio" value="anthropic" name="provider"
              disabled={loading}
              checked={statusData.configured_provider === 'anthropic'}
              onChange={handleProviderSwitch}
            />
            Force Anthropic
          </label>
          <label>
            <input
              type="radio" value="ollama" name="provider"
              disabled={loading}
              checked={statusData.configured_provider === 'ollama'}
              onChange={handleProviderSwitch}
            />
            Force Ollama
          </label>
        </div>
        <p className="text-muted" style={{ fontSize: '11px', marginTop: '8px' }}>
          Falls back automatically if the forced selection is offline.
        </p>
      </div>
    </div>
  )
}

// --------------------------------------------------------------------------
// RightPanel
// --------------------------------------------------------------------------
export default function RightPanel({
  activeTab, onTabChange, sources, artifact, mobileVisible, mobilePanel,
}) {
  const effTab = mobileVisible
    ? (mobilePanel === 'artifact' ? 'Artifact' : mobilePanel === 'sources' ? 'Sources' : activeTab)
    : activeTab

  // Auto-switch to Artifact tab when a new artifact arrives
  useEffect(() => {
    if (artifact) onTabChange('Artifact')
  }, [artifact])   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <aside className={`right-panel ${mobileVisible === false ? 'mobile-hidden' : ''}`}>
      <nav className="panel-tabs" role="tablist" aria-label="Right panel tabs">
        {TABS.map((tab) => (
          <button
            key={tab}
            id={`tab-${tab.toLowerCase()}`}
            role="tab"
            aria-selected={effTab === tab}
            className={`tab-btn${effTab === tab ? ' active' : ''}`}
            onClick={() => onTabChange(tab)}
          >
            {tab}
          </button>
        ))}
      </nav>

      <div
        className="panel-content"
        role="tabpanel"
        aria-labelledby={`tab-${effTab.toLowerCase()}`}
      >
        {effTab === 'Artifact' && <ArtifactTab artifact={artifact} />}
        {effTab === 'Sources'  && <SourcesTab  sources={sources}   />}
        {effTab === 'Model'    && <ModelTab />}
      </div>
    </aside>
  )
}

/**
 * RightPanel — Artifacts, Sources, and Model controls
 */

import { useState, useEffect } from 'react'
import Markdown from 'react-markdown'

const TABS = ['Artifact', 'Sources', 'Model']
const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function ArtifactTab({ artifact }) {
  const [viewRaw, setViewRaw] = useState(false)

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
          Artifacts will appear here after the assistant generates a structured response.
        </p>
      </div>
    )
  }

  const isHtml = artifact.type === 'html'

  return (
    <div className="artifact-container">
      <div className="artifact-header">
        <span className="artifact-badge">{artifact.type.toUpperCase()}</span>
        {isHtml && (
          <button className="btn-minimal" onClick={() => setViewRaw(!viewRaw)}>
            {viewRaw ? 'View Rendered' : 'View Source'}
          </button>
        )}
      </div>

      <div className="artifact-body">
        {isHtml && !viewRaw ? (
          <div className="iframe-wrapper">
            <iframe
              title="Rendered UI"
              srcDoc={artifact.content}
              sandbox="" // Strict sandbox: no script execution, no top navigation
              style={{ width: '100%', height: '400px', border: 'none', background: '#fff' }}
            />
          </div>
        ) : isHtml && viewRaw ? (
          <pre className="code-block">
            <code>{artifact.content}</code>
          </pre>
        ) : (
          <div className="markdown-artifact">
            <Markdown>{artifact.content}</Markdown>
          </div>
        )}
      </div>
    </div>
  )
}

function SourcesTab({ sources }) {
  if (!sources || sources.length === 0) {
    return <p className="text-muted" style={{ fontSize: '12px' }}>No sources retrieved for current context.</p>
  }

  return (
    <div>
      <p className="text-muted" style={{ fontSize: '11px', marginBottom: '12px' }}>
        {sources.length} sources cited
      </p>
      {sources.map((s, idx) => (
        <div key={idx} className="source-chip">
          <div className="source-episode">
            <span className="source-index">[{idx + 1}]</span> {s.episode_title}
          </div>
          <div className="source-meta">
            {s.segment_timestamp && <span>{s.segment_timestamp} · </span>}
            {s.relevance_score !== null && <span>Score: {s.relevance_score.toFixed(3)}</span>}
          </div>
          {s.source_url && (
            <a href={s.source_url} target="_blank" rel="noreferrer" className="source-link">Watch on YouTube ↗</a>
          )}
        </div>
      ))}
    </div>
  )
}

function ModelTab() {
  const [statusData, setStatusData] = useState(null)
  const [loading, setLoading] = useState(false)

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API}/model/status`)
      const json = await res.json()
      setStatusData(json.data)
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    fetchStatus()
  }, [])

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
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  if (!statusData) return <div className="text-muted">Loading model status...</div>

  // Determine pill status
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
            <input type="radio" value="auto" name="provider" 
              disabled={loading}
              checked={!['anthropic','ollama'].includes(statusData.configured_provider) || true} // Simplifying state for override
              onChange={handleProviderSwitch} />
            Auto (Env default)
          </label>
          <label>
            <input type="radio" value="anthropic" name="provider" 
              disabled={loading}
               onChange={handleProviderSwitch} />
            Force Anthropic
          </label>
          <label>
            <input type="radio" value="ollama" name="provider" 
              disabled={loading}
              onChange={handleProviderSwitch} />
            Force Ollama
          </label>
        </div>
        <p className="text-muted" style={{ fontSize: '11px', marginTop: '8px' }}>
          Currently active provider will fallback if forced selection is offline.
        </p>
      </div>
    </div>
  )
}

export default function RightPanel({ activeTab, onTabChange, sources, artifact, mobileVisible, mobilePanel }) {
  // Always show on desktop. On mobile, show only if mobilePanel matches one of the tabs
  const isMobileArtifact = mobileVisible && mobilePanel === 'artifact'
  const isMobileSources = mobileVisible && mobilePanel === 'sources'

  // If mobile, force the activeTab to match mobilePanel to keep things in sync
  const effTab = mobileVisible ? (mobilePanel === 'artifact' ? 'Artifact' : (mobilePanel === 'sources' ? 'Sources' : activeTab)) : activeTab

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

      <div className="panel-content" role="tabpanel" aria-labelledby={`tab-${effTab.toLowerCase()}`}>
        {effTab === 'Artifact' && <ArtifactTab artifact={artifact} />}
        {effTab === 'Sources' && <SourcesTab sources={sources} />}
        {effTab === 'Model' && <ModelTab />}
      </div>
    </aside>
  )
}

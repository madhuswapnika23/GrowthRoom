/**
 * SessionsRail — left panel
 * Dynamic list of conversation sessions from the DB.
 */

function GroundingBadge({ score }) {
  if (score === null || score === undefined) return null
  let color = 'var(--color-bg-secondary)'
  let label = 'N/A'
  if (score >= 0.8) { color = '#34d399'; label = 'High' }
  else if (score >= 0.5) { color = '#fbbf24'; label = 'Medium' }
  else if (score >= 0.1) { color = '#f87171'; label = 'Low' }
  else { color = '#6b7280'; label = 'Empty' }

  return (
    <div className="grounding-badge" style={{ backgroundColor: color }} title={`Avg grounding score: ${score}`}>
      {label}
    </div>
  )
}

export default function SessionsRail({ sessions, activeSessionId, onSelect, onNew, onDelete, mobileVisible }) {
  return (
    <aside className={`sessions-rail ${mobileVisible === false ? 'mobile-hidden' : ''}`}>
      <div className="rail-header">
        <h3>Conversations</h3>
        <button className="btn-new-session" onClick={onNew}>+ New session</button>
      </div>

      <nav className="session-list" aria-label="Session history">
        {sessions.map((s) => {
          const isActive = s.session_id === activeSessionId
          const date = new Date(s.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' })
          const time = new Date(s.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

          return (
            <div
              key={s.session_id}
              className={`session-item${isActive ? ' active' : ''}`}
              role="button"
              tabIndex={0}
              aria-current={isActive ? 'page' : undefined}
              onClick={() => onSelect(s.session_id)}
            >
              <div className="session-title-row">
                <div className="session-title" title={s.title}>{s.title}</div>
                <button 
                  className="btn-delete-session" 
                  onClick={(e) => { e.stopPropagation(); onDelete(s.session_id) }}
                  title="Delete session"
                  aria-label="Delete session"
                >×</button>
              </div>
              <div className="session-meta">
                <span>{date} {time}</span>
                <div className="session-meta-pills">
                  {s.artifact_count > 0 && (
                    <span className="artifact-pill">{s.artifact_count} docs</span>
                  )}
                  <GroundingBadge score={s.latest_grounding_score} />
                </div>
              </div>
            </div>
          )
        })}
        {sessions.length === 0 && (
          <div className="text-muted" style={{ padding: '20px', fontSize: '13px', textAlign: 'center' }}>
            No past conversations yet.
          </div>
        )}
      </nav>
    </aside>
  )
}

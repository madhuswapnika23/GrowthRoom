/**
 * App — root component + global state
 *
 * Manages:
 *  - activeSessionId, sessions list
 *  - messages, sources, artifact for the active session
 *  - rightPanelTab (Artifact | Sources | Model)
 *  - mobile panel view (chat | sources | artifact)
 */

import { useState, useEffect, useCallback } from 'react'
import SessionsRail from './components/SessionsRail'
import ConversationLog from './components/ConversationLog'
import RightPanel from './components/RightPanel'

const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export default function App() {
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [activeSources, setActiveSources] = useState([])
  const [activeArtifact, setActiveArtifact] = useState(null)
  const [rightTab, setRightTab] = useState('Sources')
  const [loading, setLoading] = useState(false)
  const [sessionLoading, setSessionLoading] = useState(false)
  const [error, setError] = useState(null)
  // Mobile panel: 'chat' | 'sources' | 'artifact'
  const [mobilePanel, setMobilePanel] = useState('chat')

  // ── Fetch session list ──────────────────────────────────────────────────
  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API}/sessions`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setSessions(json.data || [])
    } catch (e) {
      console.error('Failed to fetch sessions:', e)
    }
  }, [])

  useEffect(() => { fetchSessions() }, [fetchSessions])

  // ── Load session messages ───────────────────────────────────────────────
  const loadSession = useCallback(async (sessionId) => {
    setActiveSessionId(sessionId)
    setActiveSources([])
    setActiveArtifact(null)
    setError(null)
    setSessionLoading(true)
    try {
      const res = await fetch(`${API}/sessions/${sessionId}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      setMessages(json.data.messages || [])
      // Restore last sources/artifact
      const lastAssistant = [...(json.data.messages || [])].reverse().find(m => m.role === 'assistant')
      if (lastAssistant) {
        if (lastAssistant.sources?.length) setActiveSources(lastAssistant.sources)
        if (lastAssistant.artifact) setActiveArtifact(lastAssistant.artifact)
      }
    } catch (e) {
      setError('Failed to load session. Please try again.')
    } finally {
      setSessionLoading(false)
    }
  }, [])

  // ── New session ─────────────────────────────────────────────────────────
  const newSession = () => {
    setActiveSessionId(null)
    setMessages([])
    setActiveSources([])
    setActiveArtifact(null)
    setError(null)
    setRightTab('Sources')
  }

  // ── Send message ────────────────────────────────────────────────────────
  const sendMessage = useCallback(async (text) => {
    if (!text.trim() || loading) return
    setError(null)
    setLoading(true)

    // Optimistic user message
    const userMsg = { id: `tmp-${Date.now()}`, role: 'user', content: text, created_at: new Date().toISOString() }
    setMessages(prev => [...prev, userMsg])

    try {
      const res = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: activeSessionId || undefined,
          message: text,
        }),
      })

      const json = await res.json()

      if (!res.ok) {
        const errMsg = json?.detail || json?.error?.message || `Server error ${res.status}`
        setError(errMsg)
        setMessages(prev => prev.filter(m => m.id !== userMsg.id))
        return
      }

      const data = json.data
      // Update session id if new
      if (!activeSessionId) setActiveSessionId(data.session_id)

      const assistantMsg = {
        id: data.message_id,
        role: 'assistant',
        content: data.content,
        created_at: new Date().toISOString(),
        skill_used: data.skill_used,
        grounding_score: data.grounding_score,
        sources: data.sources || [],
        artifact: data.artifact || null,
      }

      setMessages(prev => [...prev, assistantMsg])
      setActiveSources(data.sources || [])
      if (data.artifact) {
        setActiveArtifact(data.artifact)
        setRightTab('Artifact')
      } else if (data.sources?.length) {
        setRightTab('Sources')
      }
      // Refresh sessions list
      fetchSessions()
    } catch (e) {
      setError('Could not reach the server. Is the backend running?')
      setMessages(prev => prev.filter(m => m.id !== userMsg.id))
    } finally {
      setLoading(false)
    }
  }, [activeSessionId, loading, fetchSessions])

  // ── Delete session ──────────────────────────────────────────────────────
  const deleteSession = useCallback(async (sessionId) => {
    try {
      await fetch(`${API}/sessions/${sessionId}`, { method: 'DELETE' })
      if (sessionId === activeSessionId) newSession()
      fetchSessions()
    } catch (e) {
      console.error('Failed to delete session:', e)
    }
  }, [activeSessionId, fetchSessions])

  return (
    <div className="app-shell">
      {/* Top header bar */}
      <header className="header-bar">
        <span className="logo">Growth<span>Room</span></span>
        <div className="header-right">
          {/* Mobile panel switcher */}
          <div className="mobile-panel-tabs" role="tablist" aria-label="Panel navigation">
            {['chat', 'sources', 'artifact'].map(p => (
              <button
                key={p}
                role="tab"
                aria-selected={mobilePanel === p}
                className={`mobile-tab-btn${mobilePanel === p ? ' active' : ''}`}
                onClick={() => setMobilePanel(p)}
              >
                {p === 'chat' ? '💬' : p === 'sources' ? '📚' : '📄'}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* Left — sessions rail */}
      <SessionsRail
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelect={loadSession}
        onNew={newSession}
        onDelete={deleteSession}
        mobileVisible={mobilePanel === 'chat'}
      />

      {/* Center — conversation log */}
      <ConversationLog
        messages={messages}
        loading={loading}
        sessionLoading={sessionLoading}
        error={error}
        onSend={sendMessage}
        onCitationClick={(idx) => { setRightTab('Sources'); setMobilePanel('sources') }}
        mobileVisible={mobilePanel === 'chat'}
      />

      {/* Right — tabbed panel */}
      <RightPanel
        activeTab={rightTab}
        onTabChange={setRightTab}
        sources={activeSources}
        artifact={activeArtifact}
        mobileVisible={mobilePanel === 'sources' || mobilePanel === 'artifact'}
        mobilePanel={mobilePanel}
      />
    </div>
  )
}

/**
 * ConversationLog — center panel
 * Renders user and assistant messages, inline citations, and grounding meters.
 */

import { useRef, useEffect } from 'react'
import Markdown from 'react-markdown'

function GroundingMeter({ score, skillUsed }) {
  if (skillUsed !== 'grounding_score' && score === undefined) return null

  const isLow = score === 0 || score < 0.1
  const label = isLow ? 'Not enough source material' : 'Grounding Confidence'
  const pct = isLow ? 100 : Math.round(score * 100)
  const barClass = isLow ? 'meter-bar bg-empty' : 'meter-bar bg-high'

  return (
    <div className={`grounding-meter-container ${isLow ? 'empty' : ''}`}>
      <div className="meter-label">
        <span>{label}</span>
        {!isLow && <span>{pct}%</span>}
      </div>
      <div className="meter-track">
        <div className={barClass} style={{ width: `${pct}%` }}></div>
      </div>
    </div>
  )
}

function processContentWithCitations(content, onClickCitation) {
  // If we just want standard markdown, react-markdown handles it.
  // We can write a custom plugin or wrapper to intercept `[1]` format,
  // but for simplicity, we map text here if we want native click handlers easily,
  // or we pass a custom component to Markdown matching links.
  return content
}

export default function ConversationLog({ messages, loading, sessionLoading, error, onSend, onCitationClick, mobileVisible }) {
  const inputRef = useRef(null)
  const scrollRef = useRef(null)

  // Scroll to bottom on new message
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo(0, scrollRef.current.scrollHeight)
    }
  }, [messages, loading])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      const val = inputRef.current.value
      if (val) {
        onSend(val)
        inputRef.current.value = ''
      }
    }
  }

  const handleSend = () => {
    const val = inputRef.current.value
    if (val) {
      onSend(val)
      inputRef.current.value = ''
    }
  }

  // Intercept `[number]` citations in Markdown 
  // A simplistic approach via Markdown's `a` component override if formatted as links, 
  // or simply letting text be plain if backend emits `[1](source)`. 
  // Assuming backend emits plain `[1]` text blocks, we can do a naive regex split in a real app,
  // but here we just render standard markdown.

  return (
    <main className={`conversation-log ${mobileVisible === false ? 'mobile-hidden' : ''}`}>
      <div className="conversation-scroll" ref={scrollRef}>
        {sessionLoading && (
          <div className="loading-spinner">Loading session...</div>
        )}

        {!sessionLoading && messages.length > 0 ? (
          <div className="conversation-messages">
            {messages.map((msg) => (
              <article key={msg.id} className={`message-bubble ${msg.role}`}>
                <div className="role-label">{msg.role === 'user' ? 'You' : 'Assistant'}</div>
                
                {msg.role === 'assistant' && msg.grounding_score !== undefined && (
                  <GroundingMeter score={msg.grounding_score} skillUsed={msg.skill_used} />
                )}

                <div className="message-content">
                  {msg.role === 'user' ? (
                    <h3>{msg.content}</h3>
                  ) : (
                    <Markdown>{msg.content}</Markdown>
                  )}
                </div>
              </article>
            ))}
            {loading && (
              <article className="message-bubble assistant">
                <div className="role-label">Assistant</div>
                <div className="typing-indicator"><span>•</span><span>•</span><span>•</span></div>
              </article>
            )}
          </div>
        ) : (!sessionLoading && (
          <div className="conversation-empty">
            <h1 className="empty-title">Growth Room</h1>
            <p className="empty-sub">
              Ask anything from Lenny's podcast — strategy, metrics, frameworks, founder stories.
            </p>
          </div>
        ))}

        {error && (
          <div className="error-banner">
            <strong>Error:</strong> {error}
          </div>
        )}
      </div>

      <div className="input-bar">
        <div className="input-row">
          <textarea
            ref={inputRef}
            placeholder="Ask about product strategy, metrics, retention, GTM…"
            rows={1}
            aria-label="Message input"
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <button className="btn-send" onClick={handleSend} disabled={loading}>Send</button>
        </div>
      </div>
    </main>
  )
}

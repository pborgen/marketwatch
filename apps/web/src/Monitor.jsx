import { useEffect, useState } from "react"

function pill(status) {
  if (status === "ready") return "Ready"
  if (status === "unavailable") return "Unavailable"
  return "Offline"
}

export default function Monitor({ onSignedOut }) {
  const [agents, setAgents] = useState([])
  const [logs, setLogs] = useState({})
  const [drafts, setDrafts] = useState({})
  const [busy, setBusy] = useState({})
  const [banner, setBanner] = useState("")

  useEffect(() => {
    let gone = false

    async function refresh() {
      try {
        const response = await fetch("/api/agents", { credentials: "same-origin" })
        if (response.status === 401) {
          if (!gone) onSignedOut()
          return
        }
        const payload = await response.json()
        if (!gone) {
          setAgents(payload.agents || [])
          setBanner("")
        }
      } catch {
        if (!gone) setBanner("The monitor could not refresh agent status.")
      }
    }

    refresh()
    const timer = setInterval(refresh, 15000)
    return () => {
      gone = true
      clearInterval(timer)
    }
  }, [onSignedOut])

  function append(agentId, entries, { clear = false } = {}) {
    setLogs((current) => ({
      ...current,
      [agentId]: [...(clear ? [] : current[agentId] || []), ...entries],
    }))
  }

  async function send(agentId, prompt, reset) {
    const text = prompt.trim()
    if (!text && !reset) return
    setBusy((current) => ({ ...current, [agentId]: true }))
    try {
      const response = await fetch(`/api/agents/${agentId}/commands`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: text, reset }),
      })
      if (response.status === 401) {
        onSignedOut()
        return
      }
      const payload = await response.json()
      const entries = []
      if (text) entries.push({ who: "You", text, bad: false })
      if (payload.ok) {
        entries.push({ who: "Agent", text: payload.result || "Done.", bad: false })
        if (text) setDrafts((current) => ({ ...current, [agentId]: "" }))
      } else {
        entries.push({ who: "Agent", text: payload.error || "The command failed.", bad: true })
      }
      append(agentId, entries, { clear: reset && !text })
    } catch {
      append(agentId, [{ who: "Agent", text: "The monitor could not reach the server.", bad: true }])
    } finally {
      setBusy((current) => ({ ...current, [agentId]: false }))
    }
  }

  async function signOut() {
    await fetch("/logout", { method: "POST", credentials: "same-origin" })
    onSignedOut()
  }

  return (
    <>
      <header>
        <div>
          <p className="eyebrow">Agent monitor</p>
          <h1>Market Watch</h1>
        </div>
        <button type="button" className="ghost" onClick={signOut}>
          Sign out
        </button>
      </header>
      <main id="agents" aria-live="polite">
        {banner ? <p className="banner">{banner}</p> : null}
        {agents.map((agent) => (
          <article key={agent.id}>
            <div className="title">
              <h2>{agent.name}</h2>
              <span className={`pill ${agent.status}`}>{pill(agent.status)}</span>
            </div>
            <p>{agent.description}</p>
            <p className="target">
              {agent.detail}
              {agent.target ? (
                <>
                  <br />
                  {agent.target}
                </>
              ) : null}
            </p>
            <div className="prompts">
              {(agent.prompts || []).map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="prompt"
                  disabled={busy[agent.id]}
                  onClick={() => send(agent.id, prompt, false)}
                >
                  {prompt}
                </button>
              ))}
            </div>
            <textarea
              aria-label={`Command for ${agent.name}`}
              placeholder="Tell this agent what to do"
              value={drafts[agent.id] || ""}
              disabled={busy[agent.id]}
              onChange={(event) => setDrafts((current) => ({ ...current, [agent.id]: event.target.value }))}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault()
                  send(agent.id, drafts[agent.id] || "", false)
                }
              }}
            />
            <div className="actions">
              <button type="button" className="send" disabled={busy[agent.id]} onClick={() => send(agent.id, drafts[agent.id] || "", false)}>
                Send
              </button>
              <button type="button" className="ghost reset" disabled={busy[agent.id]} onClick={() => send(agent.id, "", true)}>
                New session
              </button>
            </div>
            <div className="log">
              {(logs[agent.id] || []).map((entry, index) => (
                <div className="turn" key={`${agent.id}-${index}`}>
                  <div className="who">{entry.who}</div>
                  <div className={entry.bad ? "say bad" : "say"}>{entry.text}</div>
                </div>
              ))}
            </div>
          </article>
        ))}
      </main>
    </>
  )
}

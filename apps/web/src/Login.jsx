import { useState } from "react"

export default function Login({ onSignedIn }) {
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [pending, setPending] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setPending(true)
    setError("")
    try {
      const response = await fetch("/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ password }),
      })
      if (response.ok) {
        onSignedIn()
        return
      }
      const payload = await response.json().catch(() => ({}))
      setError(payload.error || "That password is not the demo password.")
    } catch {
      setError("The monitor could not reach the server.")
    } finally {
      setPending(false)
    }
  }

  return (
    <form className="login" onSubmit={submit}>
      <p>Agent monitor</p>
      <h1>Market Watch</h1>
      <p>Sign in with the shared demo password to see the agents and send them commands.</p>
      <label htmlFor="password">Password</label>
      <input
        id="password"
        name="password"
        type="password"
        autoComplete="current-password"
        required
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <button type="submit" disabled={pending}>
        Sign in
      </button>
      <p className="error" role="alert">
        {error}
      </p>
    </form>
  )
}

import { useEffect, useState } from "react"
import Login from "./Login.jsx"
import Monitor from "./Monitor.jsx"

export default function App() {
  const [signedIn, setSignedIn] = useState(null)

  useEffect(() => {
    let gone = false
    fetch("/api/agents", { credentials: "same-origin" })
      .then((response) => {
        if (!gone) setSignedIn(response.ok)
      })
      .catch(() => {
        if (!gone) setSignedIn(false)
      })
    return () => {
      gone = true
    }
  }, [])

  if (signedIn === null) {
    return <p className="loading">Loading</p>
  }
  if (!signedIn) {
    return <Login onSignedIn={() => setSignedIn(true)} />
  }
  return <Monitor onSignedOut={() => setSignedIn(false)} />
}

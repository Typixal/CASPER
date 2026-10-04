import { useEffect, useRef, useState } from "react"

/**
 * Subscribe to the backend's /stream SSE endpoint.
 * Each event is a full collector.collect() snapshot, or
 * {generated_at: null, fatal_error | starting}.
 * @returns {{state: object, connected: boolean}}
 */
export function useLiveState() {
  const [state, setState] = useState({ generated_at: null, starting: true })
  const [connected, setConnected] = useState(false)
  const sourceRef = useRef(null)

  useEffect(() => {
    const source = new EventSource("/stream")
    sourceRef.current = source

    source.onopen = () => setConnected(true)
    source.onmessage = (event) => {
      setConnected(true)
      try {
        setState(JSON.parse(event.data))
      } catch (err) {
        // Keep the last good state on a malformed payload.
        console.error("useLiveState: could not parse SSE payload", err)
      }
    }
    source.onerror = () => setConnected(false)

    return () => {
      source.close()
      sourceRef.current = null
    }
  }, [])

  return { state, connected }
}

/**
 * Toggle the latency probe via POST /api/probe/toggle. The new state arrives
 * on the next snapshot (state.probe.enabled), so none is kept here.
 * @returns {{toggle: () => Promise<void>, pending: boolean}}
 */
export function useProbeToggle() {
  const [pending, setPending] = useState(false)

  async function toggle() {
    setPending(true)
    try {
      await fetch("/api/probe/toggle", { method: "POST" })
    } catch (err) {
      console.error("useProbeToggle: toggle request failed", err)
    } finally {
      setPending(false)
    }
  }

  return { toggle, pending }
}

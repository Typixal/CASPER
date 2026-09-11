import { useEffect, useRef, useState } from "react"

/**
 * Subscribes to the Flask backend's /stream SSE endpoint and exposes the
 * latest snapshot from collector.collect(). This is the ONLY place the
 * frontend talks to the backend for live data -- every component below
 * reads from the object this hook returns.
 *
 * Backend contract (unchanged by this redesign): each `data:` event is the
 * full JSON snapshot collector.py produces (generated_at, docker, summary,
 * nginx, scale_log, prediction, probe, probe_summary, modules, paths), or
 * {generated_at: null, fatal_error} / {generated_at: null, starting: true}.
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
        // A malformed payload should never take the whole dashboard down --
        // keep showing the last good state and log for debugging.
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
 * Flips the dashboard's own latency probe on/off via the existing
 * POST /api/probe/toggle endpoint. Returns the toggle function; the actual
 * enabled/disabled state comes back on the next SSE snapshot (state.probe.enabled),
 * so this hook does not track its own local boolean.
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

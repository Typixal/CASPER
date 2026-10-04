import { useEffect, useRef, useState } from "react"

/**
 * Number that counts from its previous value instead of snapping.
 * Non-numeric values (e.g. null before the first snapshot) render as-is.
 * @param {object} props
 * @param {number|string|null} props.value
 * @param {number} [props.duration=600] Animation length in ms.
 * @param {string} [props.className]
 */
export default function AnimatedNumber({ value, duration = 600, className = "" }) {
  const numeric = typeof value === "number" && Number.isFinite(value)
  const [display, setDisplay] = useState(numeric ? value : 0)
  const fromRef = useRef(numeric ? value : 0)
  const frameRef = useRef(0)

  useEffect(() => {
    if (!numeric) return undefined

    const from = fromRef.current
    const to = value
    if (from === to) return undefined

    const start = performance.now()
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration)
      // ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3)
      setDisplay(Math.round(from + (to - from) * eased))
      if (t < 1) {
        frameRef.current = requestAnimationFrame(tick)
      } else {
        fromRef.current = to
      }
    }
    frameRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frameRef.current)
  }, [value, numeric, duration])

  if (!numeric) return <span className={className}>{value ?? "—"}</span>
  return <span className={`tnum ${className}`}>{display}</span>
}

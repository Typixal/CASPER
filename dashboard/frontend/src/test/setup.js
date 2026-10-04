// Test environment setup (vitest + jsdom).
import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterEach } from "vitest"

// Testing Library only auto-unmounts between tests when vitest globals are
// enabled; they are not, so do it explicitly or renders pile up across tests.
afterEach(cleanup)

// jsdom has no ResizeObserver; recharts' ResponsiveContainer needs one.
// A no-op is enough -- tests assert on text and structure, not chart pixels.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}

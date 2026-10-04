// Vitest + jsdom setup.
import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterEach } from "vitest"

// Auto-cleanup needs vitest globals, which are off.
afterEach(cleanup)

// jsdom lacks ResizeObserver, which recharts' ResponsiveContainer needs.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}

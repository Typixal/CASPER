import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// CASPER dashboard frontend.
//
// This is built ONCE (or whenever the frontend source changes) with
// `npm run build`, and the output is committed under dashboard/static/dist/.
// The demo machine only ever runs `python app.py` -- no Node, no npm, no
// internet -- so `base` must point at the path Flask actually serves static
// files from, and outDir must land inside dashboard/static/ so Flask's
// built-in static handler picks it up with no app.py changes.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/static/dist/',
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
  },
})

// Copies the Vite build's HTML shell into Flask's templates/ folder.
//
// vite.config.js sets `base: '/static/dist/'`, so the asset <script>/<link>
// tags Vite writes into static/dist/index.html already point at the right
// Flask static URL -- this is a straight file copy, no path rewriting.
//
// Run automatically by `npm run build:flask` after every `vite build`, so
// nobody has to hand-edit a hashed asset filename into templates/index.html.

import { copyFileSync, existsSync } from "node:fs"
import { fileURLToPath } from "node:url"
import path from "node:path"

const here = path.dirname(fileURLToPath(import.meta.url))
const dashboardRoot = path.resolve(here, "..", "..") // frontend/scripts -> frontend -> dashboard

const src = path.join(dashboardRoot, "static", "dist", "index.html")
const destDir = path.join(dashboardRoot, "templates")
const dest = path.join(destDir, "index.html")

if (!existsSync(src)) {
  console.error(`sync-flask-template: build output not found at ${src}. Run "npm run build" first.`)
  process.exit(1)
}

if (!existsSync(destDir)) {
  console.error(`sync-flask-template: Flask templates/ folder not found at ${destDir}.`)
  process.exit(1)
}

copyFileSync(src, dest)
console.log(`sync-flask-template: copied ${src} -> ${dest}`)

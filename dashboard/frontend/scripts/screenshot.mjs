// Screenshot dashboard pages into ./screenshots/ for checking by eye.
//
//   npm run screenshot                  # all pages
//   npm run screenshot -- overview live # selected pages
//
// Needs the dashboard running and Chrome installed. Fixed viewport, no
// full-page capture: resizing replays recharts' animation mid-shot.
import { mkdirSync } from "node:fs"
import puppeteer from "puppeteer-core"

const PAGES = ["overview", "schedule", "live", "experiment", "how"]
const wanted = process.argv.slice(2).filter((a) => PAGES.includes(a))
const pages = wanted.length ? wanted : PAGES
const url = process.env.DASHBOARD_URL || "http://localhost:8050"
const chrome = process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe"

mkdirSync("screenshots", { recursive: true })
const browser = await puppeteer.launch({ executablePath: chrome, headless: "new", args: ["--no-sandbox", "--disable-gpu"] })
const page = await browser.newPage()
await page.setViewport({ width: 1600, height: Number(process.env.HEIGHT || 1300) })
const errors = []
page.on("pageerror", (e) => errors.push(e.message))
page.on("console", (m) => m.type() === "error" && errors.push(m.text()))

for (const id of pages) {
  await page.goto(`${url}/#${id}`, { waitUntil: "domcontentloaded" })
  await new Promise((r) => setTimeout(r, 4000))
  await page.screenshot({ path: `screenshots/${id}.png` })
  console.log(`screenshots/${id}.png`)
}
console.log("console errors:", errors.length ? errors : "none")
await browser.close()

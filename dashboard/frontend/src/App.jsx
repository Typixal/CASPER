import { useEffect, useState } from "react"
import ErrorBanner from "./components/ErrorBanner"
import Sidebar from "./components/Sidebar"
import { PAGES } from "./lib/pages"
import ExperimentPage from "./pages/ExperimentPage"
import HowItWorksPage from "./pages/HowItWorksPage"
import LivePage from "./pages/LivePage"
import OverviewPage from "./pages/OverviewPage"
import SchedulePage from "./pages/SchedulePage"
import { useLiveState, useProbeToggle } from "./lib/useLiveState"

const PAGE_IDS = PAGES.map((p) => p.id)
const TECHNICAL_KEY = "casper.technical"

// Page lives in the URL hash so refresh and back keep the viewer's place.
function pageFromHash() {
  const id = window.location.hash.replace(/^#/, "")
  return PAGE_IDS.includes(id) ? id : "overview"
}

// localStorage may be blocked; the setting is a convenience, never fatal.
function readTechnical() {
  try {
    return localStorage.getItem(TECHNICAL_KEY) === "1"
  } catch {
    return false
  }
}

function writeTechnical(value) {
  try {
    localStorage.setItem(TECHNICAL_KEY, value ? "1" : "0")
  } catch {
    /* storage blocked: carry on without persistence */
  }
}

/**
 * Dashboard shell: sidebar, hash-routed pages and the technical-terms setting.
 */
export default function App() {
  const { state, connected } = useLiveState()
  const { toggle: toggleProbe, pending: probePending } = useProbeToggle()
  const [page, setPage] = useState(pageFromHash)
  const [technical, setTechnical] = useState(readTechnical)

  useEffect(() => {
    const onHashChange = () => setPage(pageFromHash())
    window.addEventListener("hashchange", onHashChange)
    return () => window.removeEventListener("hashchange", onHashChange)
  }, [])

  function navigate(id) {
    window.location.hash = id
    setPage(id)
    window.scrollTo?.({ top: 0 })
  }

  function toggleTechnical() {
    setTechnical((current) => {
      writeTechnical(!current)
      return !current
    })
  }

  const comparison = state.modules?.d?.comparison ?? null

  return (
    <div className="min-h-screen lg:flex">
      <Sidebar
        page={page}
        onNavigate={navigate}
        technical={technical}
        onToggleTechnical={toggleTechnical}
        connected={connected}
      />

      <main className="min-w-0 flex-1 px-5 py-6 sm:px-8 lg:py-8">
        <div className="mx-auto max-w-350">
          <div className="mb-5">
            <ErrorBanner state={state} />
          </div>

          {page === "overview" && <OverviewPage state={state} technical={technical} onNavigate={navigate} />}
          {page === "schedule" && <SchedulePage schedule={state.schedule} technical={technical} />}
          {page === "live" && (
            <LivePage state={state} technical={technical} onToggleProbe={toggleProbe} probePending={probePending} />
          )}
          {page === "experiment" && <ExperimentPage comparison={comparison} technical={technical} />}
          {page === "how" && <HowItWorksPage />}
        </div>
      </main>
    </div>
  )
}

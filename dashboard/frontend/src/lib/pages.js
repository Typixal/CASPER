import { BookOpen, CalendarDays, FlaskConical, LayoutDashboard, Server } from "lucide-react"

// The dashboard's pages, in story order: what's happening -> what's coming ->
// the machinery -> the proof -> how it all fits. Overview is where a
// non-technical viewer lands.
export const PAGES = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "schedule", label: "Event schedule", icon: CalendarDays },
  { id: "live", label: "Live system", icon: Server },
  { id: "experiment", label: "Experiment", icon: FlaskConical },
  { id: "how", label: "How it works", icon: BookOpen },
]

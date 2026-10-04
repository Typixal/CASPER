import { BookOpen, CalendarDays, FlaskConical, LayoutDashboard, Server } from "lucide-react"

// Pages in story order; the first is the landing page.
export const PAGES = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "schedule", label: "Event schedule", icon: CalendarDays },
  { id: "live", label: "Live system", icon: Server },
  { id: "experiment", label: "Experiment", icon: FlaskConical },
  { id: "how", label: "How it works", icon: BookOpen },
]

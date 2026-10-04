import { BrainCircuit, CalendarDays, FlaskConical, Server } from "lucide-react"
import PageHeader from "../components/PageHeader"
import { glossary } from "../lib/terms"

const STEPS = [
  {
    title: "Knows the calendar",
    module: "Module A",
    icon: CalendarDays,
    text: "CASPER keeps a list of upcoming exam results and admission deadlines, with how many students registered for each. Result dates are announced in advance — that's the whole trick.",
  },
  {
    title: "Estimates the crowd",
    module: "Module B",
    icon: BrainCircuit,
    text: "From the number of students, last year's turnout, and how searches for the result usually build up, it estimates how many servers the busiest minute will need, and when the rush starts and ends.",
  },
  {
    title: "Gets servers ready",
    module: "Module C",
    icon: Server,
    text: "Shortly before the rush, CASPER starts extra copies of the portal and tells the traffic director to share visitors between them. After the rush, it removes the extras so nobody pays for idle servers.",
  },
  {
    title: "Proves it works",
    module: "Module D",
    icon: FlaskConical,
    text: "The same crowd of visitors is replayed twice: once against a normal autoscaler that waits until pages get slow, and once against CASPER. Then the two are compared.",
  },
]

// Glossary definitions, keyed like lib/terms.
const MEANING = {
  replicas: "Copies of the portal running at the same time. More copies = more visitors served at once.",
  p95: "Of every 100 page loads, how long the 5 slowest took. It shows the worst experience, not the average.",
  median: "How long a normal page load took — half were faster, half slower.",
  error_rate: "Share of visitors whose page didn't load at all.",
  success_pct: "Share of visitors whose page loaded.",
  replica_seconds: "Servers × seconds they ran. A stand-in for cost.",
  dropped: "Visitors the test couldn't even send because the portal was too backed up.",
  nginx: "Sits in front of the servers and hands each visitor to one of them.",
  probe: "A single request the dashboard sends every 2 seconds to measure how fast pages load.",
  reactive: "The normal approach: watch how slow pages are, add servers once they get slow.",
  predictive: "CASPER: add servers before the crowd arrives, from the calendar.",
  ramp_start: "When CASPER starts adding servers, ahead of the expected rush.",
  ramp_peak: "When the most visitors are expected at once.",
  ramp_end: "When CASPER starts removing the extra servers.",
  candidates: "Students registered for the exam — the main clue to how big the rush will be.",
  prediction: "Module B's output: how many servers, and from when until when.",
}

/**
 * The problem, the four modules as four steps, and the glossary.
 */
export default function HowItWorksPage() {
  const rows = glossary().filter((g) => MEANING[g.key])

  return (
    <>
      <PageHeader title="How CASPER works">
        Government exam-result portals often <b className="text-text">crash on result day</b>: millions of students
        open them in the same minute. Normal autoscalers learn from past traffic — but a portal that's quiet all year
        has none. CASPER doesn't need traffic history. It uses the calendar.
      </PageHeader>

      <ol className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {STEPS.map((step, i) => {
          const Icon = step.icon
          return (
            <li
              key={step.title}
              aria-label={`step ${i + 1}: ${step.title}`}
              className="rounded-2xl border border-border bg-panel-raised/70 p-5"
            >
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-steel/15 text-steel">
                  <Icon size={18} aria-hidden="true" />
                </span>
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-text-faint">
                    {i + 1} · {step.module}
                  </div>
                  <div className="text-[16px] font-semibold text-text">{step.title}</div>
                </div>
              </div>
              <p className="mt-3 text-[14.5px] leading-relaxed text-text-muted">{step.text}</p>
            </li>
          )
        })}
      </ol>

      <h2 className="mt-10 mb-3 text-lg font-semibold text-text">Glossary</h2>
      <p className="mb-4 text-[13.5px] text-text-muted">
        The dashboard uses the plain word by default. Switch on <i>Show technical terms</i> in the sidebar to see the
        engineering term instead.
      </p>
      <div className="overflow-x-auto rounded-xl border border-border">
        <table aria-label="Glossary" className="w-full min-w-[560px] border-collapse text-[13.5px]">
          <thead>
            <tr className="bg-panel text-left text-[11px] uppercase tracking-wider text-text-faint">
              <th className="px-4 py-2.5 font-semibold">plain word</th>
              <th className="px-4 py-2.5 font-semibold">technical term</th>
              <th className="px-4 py-2.5 font-semibold">what it means</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((g) => (
              <tr key={g.key} className="border-t border-border/60 align-top">
                <td className="px-4 py-2.5 font-medium text-text">{g.plain}</td>
                <td className="px-4 py-2.5 font-mono text-[12.5px] text-steel">{g.technical}</td>
                <td className="px-4 py-2.5 text-text-muted">{MEANING[g.key]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

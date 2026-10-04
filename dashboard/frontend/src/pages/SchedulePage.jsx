import { motion } from "framer-motion"
import { CalendarClock, CalendarX2, PlayCircle, Users } from "lucide-react"
import PageHeader from "../components/PageHeader"
import { eventName } from "../lib/narrative"
import { term } from "../lib/terms"

const KIND = {
  exam_result: "Exam results",
  admission_deadline: "Admission deadline",
  recruitment_result: "Recruitment results",
}

const dateLabel = (iso) =>
  new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })
const timeLabel = (iso) => new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })

function Forecast({ row, technical }) {
  if (row.predicted_peak_replicas == null) {
    return <span className="text-text-faint">No forecast yet — Module B has not estimated this event.</span>
  }
  const window =
    row.ramp_start && row.ramp_end ? ` · ready from ${timeLabel(row.ramp_start)} to ${timeLabel(row.ramp_end)}` : ""
  return (
    <span>
      CASPER plans <b className="text-steel">{row.predicted_peak_replicas} {term("replicas", technical)}</b>
      {window}
    </span>
  )
}

/**
 * Every Module A event with its Module B forecast and past/upcoming status.
 * @param {object} props
 * @param {object[]} props.schedule Output of collector.read_schedule().
 * @param {boolean} [props.technical=false]
 */
export default function SchedulePage({ schedule, technical = false }) {
  return (
    <>
      <PageHeader title="Event schedule">
        Every exam result and admission deadline CASPER knows about, how many students are expected, and how many{" "}
        {term("replicas", technical)} it plans to have ready. This is what "knowing the date in advance" looks like.
      </PageHeader>

      {!schedule?.length ? (
        <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-border py-12 text-text-faint">
          <CalendarX2 size={22} aria-hidden="true" />
          No events in the dataset yet.
        </div>
      ) : (
        <ol className="space-y-3">
          {schedule.map((row, i) => (
            <motion.li
              key={row.event_id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: i * 0.04 }}
              className={
                "rounded-2xl border p-4 sm:p-5 " +
                (row.demo
                  ? "border-steel/50 bg-steel/10"
                  : row.status === "past"
                    ? "border-border bg-panel/50"
                    : "border-border bg-panel-raised/80")
              }
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[16px] font-semibold text-text">{eventName(row.event_id)}</span>
                    <span
                      className={
                        "rounded-full px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wider " +
                        (row.status === "upcoming" ? "bg-green/15 text-green" : "bg-panel-hover text-text-faint")
                      }
                    >
                      {row.status}
                    </span>
                    {row.demo && (
                      <span className="flex items-center gap-1 rounded-full bg-steel/20 px-2 py-0.5 text-[10.5px] font-semibold text-steel">
                        <PlayCircle size={11} aria-hidden="true" />
                        replaying in the demo
                      </span>
                    )}
                  </div>
                  <div className="mt-1 text-[13px] text-text-muted">
                    {KIND[row.event_type] ?? row.event_type} · {row.board}
                    {technical && <span className="ml-2 font-mono text-[11px] text-text-faint">{row.event_id}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-1.5 text-[13px] text-text-muted">
                  <CalendarClock size={14} aria-hidden="true" />
                  {dateLabel(row.date)}
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-[13.5px] text-text">
                <span className="flex items-center gap-1.5">
                  <Users size={14} className="text-text-faint" aria-hidden="true" />
                  {row.registered_candidates == null
                    ? "—"
                    : `${row.registered_candidates.toLocaleString("en-US")} students registered`}
                </span>
                <Forecast row={row} technical={technical} />
              </div>
            </motion.li>
          ))}
        </ol>
      )}

      <p className="mt-6 text-[12px] text-text-faint">
        Candidate numbers are synthetic sample data (see Module A). Dates are shown as recorded — most are already past;
        the live demo replays one of them, shifted to start a few seconds from now.
      </p>
    </>
  )
}

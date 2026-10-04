import { Activity, FileCode2, History, PieChart, Radio, Server } from "lucide-react"
import AuditTable from "../components/AuditTable"
import NginxPanel from "../components/NginxPanel"
import PageHeader from "../components/PageHeader"
import Panel from "../components/Panel"
import StatRail from "../components/StatRail"
import LatencyChart from "../components/charts/LatencyChart"
import ReplicaGrid from "../components/charts/ReplicaGrid"
import ScaleTimeline from "../components/charts/ScaleTimeline"
import SourceSplitBar from "../components/charts/SourceSplitBar"

function Explain({ children }) {
  return <p className="mb-4 text-[13px] leading-relaxed text-text-muted">{children}</p>
}

/**
 * Probe on/off button. Disabled while locked during Module D's experiment
 * (the backend also refuses with 409).
 */
function ProbeButton({ probe, technical, onToggle, pending }) {
  const name = technical ? "probe" : "test visitor"
  const label = probe?.locked ? `${name} locked off` : `${name} ${probe?.enabled ? "on" : "off"}`
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={pending || probe?.locked}
      title={
        probe?.locked
          ? "Locked off while the experiment runs, so the dashboard adds no traffic to the measurement"
          : "Turn off before running a load test by hand"
      }
      className={
        "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-60 " +
        (probe?.enabled && !probe?.locked
          ? "border-steel/40 bg-steel/10 text-steel hover:bg-steel/20"
          : "border-border bg-panel/60 text-text-faint")
      }
    >
      <Radio size={13} strokeWidth={2.4} aria-hidden="true" />
      {label}
    </button>
  )
}

/**
 * Live system: stats, servers, prediction, latency and scaling history.
 * @param {object} props
 * @param {object} props.state Latest snapshot.
 * @param {boolean} [props.technical=false]
 * @param {() => void} props.onToggleProbe
 * @param {boolean} [props.probePending=false]
 */
export default function LivePage({ state, technical = false, onToggleProbe, probePending = false }) {
  const t = (plain, tech) => (technical ? tech : plain)
  const probeEnabled = state.probe?.enabled ?? true

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader title="Live system">
          The machinery underneath, updating every two seconds: how many {t("servers", "replicas")} are running, how
          fast pages load, and every time the {t("server count", "replica count")} changed and who changed it.
        </PageHeader>
        {onToggleProbe && (
          <ProbeButton probe={state.probe} technical={technical} onToggle={onToggleProbe} pending={probePending} />
        )}
      </div>

      <div className="space-y-5">
        <StatRail state={state} technical={technical} />

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <Panel icon={History} title={t("Servers over time", "Capacity over time")} className="xl:col-span-2">
            <Explain>
              Each dot is a moment the number of servers changed. Blue = CASPER planned it, orange = the wait-and-react
              autoscaler, grey = changed by hand.
            </Explain>
            <ScaleTimeline scaleLog={state.scale_log} />
            <AuditTable actions={state.scale_log?.actions} />
          </Panel>

          <Panel icon={Server} title={t("Servers running now", "Portal replicas")}>
            <Explain>
              Each card is one copy of the portal. Green means healthy and receiving visitors; the number at the
              bottom counts the dashboard's test visits it answered.
            </Explain>
            <ReplicaGrid docker={state.docker} probeSummary={state.probe_summary} technical={technical} />
          </Panel>
        </div>

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <Panel icon={Activity} title={t("How fast pages load", "Probe latency")} className="xl:col-span-2">
            <Explain>
              The dashboard visits the portal every two seconds and times the page load. Lower is better; red bars are
              visits that failed. This is the dashboard's own visitor, not the experiment's traffic.
            </Explain>
            <LatencyChart probeSummary={state.probe_summary} probeEnabled={probeEnabled} />
          </Panel>

          <div className="space-y-5">
            <Panel icon={PieChart} title={t("Who changed the server count", "Scaling source split")}>
              <Explain>Every change ever recorded, split by who made it.</Explain>
              <SourceSplitBar scaleLog={state.scale_log} />
            </Panel>
            <Panel icon={FileCode2} title={t("Traffic director", "nginx upstream")}>
              <Explain>
                The traffic director (nginx) hands each visitor to one of the servers listed here. A server only gets
                visitors once it's on this list.
              </Explain>
              <NginxPanel nginx={state.nginx} />
            </Panel>
          </div>
        </div>
      </div>
    </>
  )
}

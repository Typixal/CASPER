import { Activity, FileCode2, History, PieChart, Server } from "lucide-react"
import Masthead from "./components/Masthead"
import ErrorBanner from "./components/ErrorBanner"
import StatRail from "./components/StatRail"
import Panel from "./components/Panel"
import AuditTable from "./components/AuditTable"
import NginxPanel from "./components/NginxPanel"
import ModulePanel from "./components/ModulePanel"
import PredictionRamp from "./components/charts/PredictionRamp"
import ScaleTimeline from "./components/charts/ScaleTimeline"
import LatencyChart from "./components/charts/LatencyChart"
import ReplicaGrid from "./components/charts/ReplicaGrid"
import SourceSplitBar from "./components/charts/SourceSplitBar"
import { useLiveState, useProbeToggle } from "./lib/useLiveState"

export default function App() {
  const { state, connected } = useLiveState()
  const { toggle, pending } = useProbeToggle()

  const modules = state.modules ?? {}
  const probeEnabled = state.probe?.enabled ?? true

  return (
    <div className="min-h-screen">
      <Masthead
        entrypoint={state.paths?.entrypoint}
        connected={connected}
        probeEnabled={probeEnabled}
        onToggleProbe={toggle}
        probePending={pending}
      />

      <main className="mx-auto max-w-[1600px] space-y-5 px-5 py-5">
        <ErrorBanner state={state} />

        {/* 1 — The claim: CASPER knows what's coming and when it will act */}
        <PredictionRamp
          prediction={state.prediction}
          currentReplicas={state.summary?.replicas_ready}
        />

        {/* 2 — The numbers behind it */}
        <StatRail state={state} />

        {/* 3 — The proof: capacity moved, and who moved it */}
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <Panel
            icon={History}
            title="Capacity over time"
            tag="oldest → newest"
            className="xl:col-span-2"
            delay={0.1}
          >
            <ScaleTimeline scaleLog={state.scale_log} />
            <AuditTable actions={state.scale_log?.actions} />
          </Panel>

          <Panel icon={Server} title="Portal replicas" tag="live from docker" delay={0.15}>
            <ReplicaGrid docker={state.docker} probeSummary={state.probe_summary} />
          </Panel>
        </div>

        {/* 4 — What the traffic actually experienced */}
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <Panel
            icon={Activity}
            title="Probe latency"
            tag="dashboard's own request · not k6"
            className="xl:col-span-2"
            delay={0.2}
          >
            <LatencyChart probeSummary={state.probe_summary} probeEnabled={probeEnabled} />
          </Panel>

          <div className="space-y-5">
            <Panel icon={PieChart} title="Who scaled it" tag="all-time" delay={0.25}>
              <SourceSplitBar scaleLog={state.scale_log} />
            </Panel>
            <Panel icon={FileCode2} title="nginx upstream" tag="generated config" delay={0.3}>
              <NginxPanel nginx={state.nginx} />
            </Panel>
          </div>
        </div>

        {/* 5 — Where the rest of the system stands */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <ModulePanel title="Module A — event dataset" module={modules.a} delay={0.35}>
            {modules.a?.built ? (
              <>
                <div className="text-text">{modules.a.detail}</div>
                {(modules.a.events ?? []).map((e) => (
                  <div key={e.event_id} className="flex justify-between font-mono text-[11px]">
                    <span>{e.event_id}</span>
                    <span className="tnum text-text-faint">{e.registered_candidates}</span>
                  </div>
                ))}
              </>
            ) : (
              <>
                <div>
                  expects <code className="font-mono text-text-muted">module-a-ingestion/events.json</code>
                </div>
                <div>lights up on its own once that file exists</div>
              </>
            )}
          </ModulePanel>

          <ModulePanel title="Module B — estimation model" module={modules.b} delay={0.4}>
            {modules.b?.built ? (
              <>
                <div className="text-text">{modules.b.detail}</div>
                {(modules.b.files ?? []).map((f) => (
                  <div key={f} className="font-mono text-[11px]">
                    {f}
                  </div>
                ))}
              </>
            ) : (
              <>
                <div>
                  expects{" "}
                  <code className="font-mono text-text-muted">module-b-estimation/predictions/*.json</code>
                </div>
                <div>Module C is running on its hand-authored sample Prediction</div>
              </>
            )}
          </ModulePanel>

          <ModulePanel title="Module D — reactive baseline & k6" module={modules.d} delay={0.45}>
            {modules.d?.built ? (
              <>
                <div className="text-text">{modules.d.detail}</div>
                {[...(modules.d.k6_scripts ?? []), ...(modules.d.results ?? [])].map((f) => (
                  <div key={f} className="font-mono text-[11px]">
                    {f}
                  </div>
                ))}
              </>
            ) : (
              <>
                <div>
                  expects <code className="font-mono text-text-muted">module-d-evaluation/</code> k6 scripts
                  and results
                </div>
                <div>
                  its actions will appear above tagged{" "}
                  <span className="font-semibold text-amber">reactive</span>
                </div>
              </>
            )}
          </ModulePanel>
        </div>

        <footer className="pb-6 pt-1 text-[11px] leading-relaxed text-text-faint">
          Read-only view — the dashboard never scales anything. It reads Docker state,{" "}
          <code className="font-mono">nginx/nginx.conf</code>,{" "}
          <code className="font-mono">logs/scale_actions.jsonl</code> and the active Prediction.
        </footer>
      </main>
    </div>
  )
}

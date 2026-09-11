import Masthead from "./components/Masthead"
import ErrorBanner from "./components/ErrorBanner"
import Hero from "./components/Hero"
import StatRail from "./components/StatRail"
import Panel from "./components/Panel"
import AuditTable from "./components/AuditTable"
import NginxPanel from "./components/NginxPanel"
import ModulePanel from "./components/ModulePanel"
import ScaleTimeline from "./components/charts/ScaleTimeline"
import LatencyChart from "./components/charts/LatencyChart"
import ReplicaGrid from "./components/charts/ReplicaGrid"
import SourceSplitBar from "./components/charts/SourceSplitBar"
import { useLiveState, useProbeToggle } from "./lib/useLiveState"

export default function App() {
  const { state, connected } = useLiveState()
  const { toggle, pending } = useProbeToggle()

  const modules = state.modules ?? {}

  return (
    <div className="min-h-screen bg-bg text-text">
      <Masthead
        entrypoint={state.paths?.entrypoint}
        connected={connected}
        probeEnabled={state.probe?.enabled ?? true}
        onToggleProbe={toggle}
        probePending={pending}
      />

      <ErrorBanner state={state} />

      <Hero prediction={state.prediction} />

      <StatRail state={state} />

      <main className="mx-auto flex max-w-350 flex-col gap-6 px-4 py-6 sm:px-6">
        {/* Centerpiece: the scaling-event story, oldest -> newest */}
        <Panel title="Scale action timeline" tag="predicted event → planned → executed">
          <ScaleTimeline scaleLog={state.scale_log} generatedAt={state.generated_at} />
          <AuditTable actions={state.scale_log?.actions} />
        </Panel>

        {/* Traffic result: what actually happened */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Panel title="Probe latency" tag="dashboard's own request, 1 per refresh">
            <LatencyChart probeSummary={state.probe_summary} />
          </Panel>
          <Panel title="Portal replicas" tag="module c · live from docker">
            <ReplicaGrid docker={state.docker} probeSummary={state.probe_summary} />
          </Panel>
        </div>

        {/* Supporting detail */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Panel title="Scaling source split" tag="all-time">
            <SourceSplitBar scaleLog={state.scale_log} />
          </Panel>
          <Panel title="nginx upstream" tag="generated config">
            <NginxPanel nginx={state.nginx} />
          </Panel>
        </div>

        {/* Module status strip */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <ModulePanel title="Module A — event dataset" module={modules.a}>
            {modules.a?.built ? (
              <>
                <div className="mb-1">{modules.a.detail}</div>
                {(modules.a.events ?? []).map((e) => (
                  <div key={e.event_id} className="flex justify-between font-mono text-[11px]">
                    <span>{e.event_id}</span>
                    <span className="text-text-muted">{e.registered_candidates}</span>
                  </div>
                ))}
              </>
            ) : (
              <>
                expects <code className="font-mono">module-a-ingestion/events.json</code>
                <br />
                panel lights up automatically once that file exists
              </>
            )}
          </ModulePanel>

          <ModulePanel title="Module B — estimation output" module={modules.b}>
            {modules.b?.built ? (
              <>
                <div className="mb-1">{modules.b.detail}</div>
                {(modules.b.files ?? []).map((f) => (
                  <div key={f} className="font-mono text-[11px]">
                    {f}
                  </div>
                ))}
              </>
            ) : (
              <>
                expects <code className="font-mono">module-b-estimation/predictions/*.json</code>
                <br />
                Module C currently runs on its hand-authored sample Prediction
              </>
            )}
          </ModulePanel>

          <ModulePanel title="Module D — reactive baseline & k6" module={modules.d}>
            {modules.d?.built ? (
              <>
                <div className="mb-1">{modules.d.detail}</div>
                {(modules.d.k6_scripts ?? []).map((f) => (
                  <div key={f} className="font-mono text-[11px] text-text-muted">
                    {f} <span className="text-text-faint">k6 script</span>
                  </div>
                ))}
                {(modules.d.results ?? []).map((f) => (
                  <div key={f} className="font-mono text-[11px] text-text-muted">
                    {f} <span className="text-text-faint">result</span>
                  </div>
                ))}
              </>
            ) : (
              <>
                expects <code className="font-mono">module-d-evaluation/k6/*.js</code> and{" "}
                <code className="font-mono">module-d-evaluation/results/*.json</code>
                <br />
                once the reactive baseline runs, its actions appear in the timeline above tagged{" "}
                <span className="font-semibold text-amber">reactive</span>
              </>
            )}
          </ModulePanel>
        </div>
      </main>

      <footer className="mx-auto max-w-350 px-4 pb-8 text-xs text-text-muted sm:px-6">
        Read-only view. The dashboard never scales anything — it reads Docker state,{" "}
        <code className="font-mono">nginx/nginx.conf</code>,{" "}
        <code className="font-mono">logs/scale_actions.jsonl</code> and the active Prediction.
      </footer>
    </div>
  )
}

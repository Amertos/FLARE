import { useEffect, useRef, useState } from "react";
import { api, sourceLabel, type Experiment } from "../api";
import { ScreenHeader } from "../ui/FlarePanel";

const VERDICT_STYLES: Record<string, string> = {
  spread: "bg-red-900/50 text-red-300 border-red-800",
  "self-extinguish": "bg-emerald-900/50 text-emerald-300 border-emerald-800",
  extinguished: "bg-sky-900/50 text-sky-300 border-sky-800",
};

const KIND_STYLES: Record<string, string> = {
  experiment: "bg-slate-800 text-slate-200 border-slate-600",
  historical: "bg-amber-950/60 text-amber-300 border-amber-800",
  specification: "bg-sky-950/60 text-sky-300 border-sky-800",
};

const KIND_SHORT: Record<string, string> = {
  experiment: "experiment",
  historical: "historical fire",
  specification: "specification",
};

type Filter = "all" | "experiment";

export default function EvidenceExplorer({
  query,
  focus,
}: {
  query: string;
  /** Record a citation chip asked for. The shell remounts this component with a
   *  new key when it changes, so the open card and the highlight are derived
   *  from the prop at mount instead of being written back in an effect. */
  focus?: string | null;
}) {
  const [results, setResults] = useState<Experiment[]>([]);
  const [counts, setCounts] = useState({ evidence: 0, context: 0 });
  const [open, setOpen] = useState<string | null>(focus ?? null);
  const [highlight, setHighlight] = useState<string | null>(focus ?? null);
  const [filter, setFilter] = useState<Filter>("all");
  const [err, setErr] = useState<string | null>(null);
  const highlightTimer = useRef<number | null>(null);

  useEffect(() => {
    let alive = true;
    api.experiments(query)
      .then((r) => {
        if (!alive) return;
        setResults(r.results);
        setCounts({ evidence: r.evidence_count, context: r.context_count });
        setErr(null);
      })
      .catch((e) => alive && setErr(String(e)));
    return () => { alive = false; };
  }, [query]);

  // Bringing a cited record into view is DOM work, not state: scroll to it
  // once the rows exist and let the highlight fade on a timer.
  useEffect(() => {
    if (!focus || results.length === 0) return;
    let raf = 0;
    const id = window.setTimeout(() => {
      raf = requestAnimationFrame(() => {
        document.getElementById(`exp-${focus}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
      });
      highlightTimer.current = window.setTimeout(() => setHighlight(null), 2500);
    }, 0);
    return () => {
      window.clearTimeout(id);
      cancelAnimationFrame(raf);
    };
  }, [focus, results]);

  useEffect(() => () => {
    if (highlightTimer.current) window.clearTimeout(highlightTimer.current);
  }, []);

  if (err) return <div className="text-red-300 text-sm p-6">Failed to load experiments: {err}</div>;

  const shown = filter === "experiment"
    ? results.filter((e) => e.record_kind === "experiment")
    : results;

  return (
    <div className="space-y-3 screen-enter">
      <ScreenHeader
        eyebrow="Screen 5 · The data"
        title="Evidence Explorer"
        lede="NASA experiments ranked by condition similarity to the current scenario. Every record links to its source — click a card for the full experimental conditions."
      />

      <div className="flex flex-wrap items-center gap-3">
        <p className="text-sm text-slate-400 flex-1 min-w-[18rem] sr-only">
          Ranked experiment records with filter controls.
        </p>
        <div className="flex gap-1 text-xs" role="group" aria-label="Filter records by kind">
          {([
            { id: "all", label: `All ${results.length}` },
            { id: "experiment", label: `Combustion experiments ${counts.evidence}` },
          ] as Array<{ id: Filter; label: string }>).map((f) => (
            <button key={f.id} onClick={() => setFilter(f.id)}
              aria-pressed={filter === f.id}
              className={`px-2.5 py-1 rounded border ${filter === f.id
                ? "border-orange-600 bg-orange-950/40 text-orange-200"
                : "border-slate-700 bg-slate-900/60 text-slate-300 hover:bg-slate-800"}`}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <p className="text-[11px] text-slate-500">
        {counts.evidence} records are controlled combustion experiments. {counts.context} are
        context records — an atmosphere specification and a historical fire — that carry no
        combustion verdict and are never counted as fire evidence (dossier §6.1).
      </p>

      {shown.map((e) => (
        <div key={e.experiment_id} id={`exp-${e.experiment_id}`}
          className={`bg-slate-900/60 border rounded-lg transition-shadow ${highlight === e.experiment_id
            ? "border-orange-500 ring-2 ring-orange-500/60"
            : "border-slate-800"}`}>
          <button className="w-full text-left px-4 py-3 flex flex-wrap items-center gap-3"
            aria-expanded={open === e.experiment_id}
            onClick={() => setOpen(open === e.experiment_id ? null : e.experiment_id)}>
            <span className="font-mono font-semibold text-orange-300">{e.experiment_id}</span>
            <span className="text-sm text-slate-300">{e.mission}</span>
            <span className="text-xs text-slate-500">{e.platform} · {e.year}</span>
            <span className={`text-[10px] px-2 py-0.5 rounded border ${KIND_STYLES[e.record_kind] ?? "bg-slate-800 text-slate-300 border-slate-700"}`}>
              {KIND_SHORT[e.record_kind] ?? e.record_kind}
            </span>
            <span className={`ml-auto text-[10px] px-2 py-0.5 rounded border ${VERDICT_STYLES[e.verdict] ?? "bg-slate-800 text-slate-300 border-slate-700"}`}>
              {e.verdict}
            </span>
            {e.similarity != null && (
              <span className="font-mono text-xs text-slate-400">sim {(e.similarity * 100).toFixed(0)}%</span>
            )}
          </button>
          {open === e.experiment_id && (
            <div className="px-4 pb-4 pt-1 border-t border-slate-800 grid md:grid-cols-2 gap-x-6 gap-y-1 text-xs">
              <div><span className="text-slate-500">Material:</span> {e.material}</div>
              <div><span className="text-slate-500">Class:</span> {e.material_class}</div>
              <div><span className="text-slate-500">Pressure:</span> {e.pressure_kpa} kPa</div>
              <div><span className="text-slate-500">O₂:</span> {e.o2_pct}%</div>
              <div><span className="text-slate-500">Gravity:</span> {e.gravity}</div>
              <div><span className="text-slate-500">Flow:</span> {e.flow_ms} m/s</div>
              <div><span className="text-slate-500">Geometry:</span> {e.geometry}</div>
              <div><span className="text-slate-500">Outcome:</span> {e.outcome_type}</div>
              {e.record_kind !== "experiment" && (
                <div className="md:col-span-2 mt-1 text-amber-300/90">
                  {e.record_kind_label} — this record has no combustion verdict, so it is shown for
                  context and is never cited as fire evidence.
                </div>
              )}
              <div className="md:col-span-2 mt-1 text-slate-300">{e.notes}</div>
              <div className="md:col-span-2 mt-1">
                <a className="text-sky-300 hover:underline font-mono" href={e.source_url}
                  target="_blank" rel="noreferrer">
                  View source — {sourceLabel(e)} ↗
                </a>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

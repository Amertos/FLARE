import { useEffect, useState } from "react";
import { api, type Experiment } from "../api";

const VERDICT_STYLES: Record<string, string> = {
  spread: "bg-red-900/50 text-red-300 border-red-800",
  "self-extinguish": "bg-emerald-900/50 text-emerald-300 border-emerald-800",
  extinguished: "bg-sky-900/50 text-sky-300 border-sky-800",
};

export default function EvidenceExplorer({ query }: { query: string }) {
  const [results, setResults] = useState<Experiment[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.experiments(query)
      .then((r) => alive && setResults(r.results))
      .catch((e) => alive && setErr(String(e)));
    return () => { alive = false; };
  }, [query]);

  if (err) return <div className="text-red-300 text-sm p-6">Failed to load experiments: {err}</div>;

  return (
    <div className="space-y-3">
      <div className="text-sm text-slate-400">
        NASA experiments ranked by condition similarity to the current scenario.
        Every record links to its source — click a card for the full experimental conditions.
      </div>
      {results.map((e) => (
        <div key={e.experiment_id} className="bg-slate-900/60 border border-slate-800 rounded-lg">
          <button className="w-full text-left px-4 py-3 flex flex-wrap items-center gap-3"
            onClick={() => setOpen(open === e.experiment_id ? null : e.experiment_id)}>
            <span className="font-mono font-semibold text-orange-300">{e.experiment_id}</span>
            <span className="text-sm text-slate-300">{e.mission}</span>
            <span className="text-xs text-slate-500">{e.platform} · {e.year}</span>
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
              <div className="md:col-span-2 mt-1 text-slate-300">{e.notes}</div>
              <div className="md:col-span-2 mt-1">
                <a className="text-sky-300 hover:underline font-mono" href={e.source_url} target="_blank" rel="noreferrer">
                  View source — NTRS {e.ntrs_id} ↗
                </a>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

import { useEffect, useState } from "react";
import { api, type ValidationResponse } from "../api";

export default function Validation() {
  const [v, setV] = useState<ValidationResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.validate().then((r) => alive && setV(r)).catch((e) => alive && setErr(String(e)));
    return () => { alive = false; };
  }, []);

  if (err) return <div className="text-red-300 text-sm p-6">Failed to load validation: {err}</div>;
  if (!v) return <div className="text-slate-400 text-sm p-6">Loading backtest…</div>;

  return (
    <div className="space-y-4">
      <div className="grid md:grid-cols-3 gap-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
          <div className="text-xs text-slate-400">Leave-one-out accuracy</div>
          <div className="text-3xl font-bold font-mono mt-1">{v.accuracy != null ? (v.accuracy * 100).toFixed(1) + "%" : "—"}</div>
          <div className="text-xs text-slate-500 mt-1">{v.correct} / {v.total} experiments classified correctly</div>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
          <div className="text-xs text-slate-400">Non-anchor accuracy</div>
          <div className="text-3xl font-bold font-mono mt-1 text-emerald-300">{v.accuracy_non_anchor != null ? (v.accuracy_non_anchor * 100).toFixed(1) + "%" : "—"}</div>
          <div className="text-xs text-slate-500 mt-1">excluding records that are fit anchors of the LOC(P) curve</div>
        </div>
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
          <div className="text-xs text-slate-400">Method</div>
          <div className="text-sm mt-1 text-slate-300">{v.method}</div>
          <div className="text-xs text-slate-500 mt-1">Reproducible: <code>py -m pytest backend/tests -q</code></div>
        </div>
      </div>

      <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
        <p className="text-xs text-slate-400 mb-3">
          The engine classifies each NASA experiment's verdict (spread vs self-extinguish) from the LOC boundary built from the <em>other</em> records.
          Misses are shown with explanations — we publish our failures, not just our accuracy.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-slate-500 text-left border-b border-slate-800">
              <th className="py-2 pr-3">Experiment</th>
              <th className="pr-3">Conditions</th>
              <th className="pr-3">Observed</th>
              <th className="pr-3">Predicted</th>
              <th className="pr-3">Margin</th>
              <th>Result</th>
            </tr></thead>
            <tbody>
              {v.results.map((r) => (
                <tr key={r.experiment_id} id={`exp-${r.experiment_id}`}
                  className="border-b border-slate-800/60 align-top">
                  <td className="py-2 pr-3 font-mono text-slate-300">
                    {r.experiment_id}
                    {r.is_fit_anchor && <span className="ml-1 text-[9px] text-amber-400 border border-amber-800 rounded px-1">anchor</span>}
                  </td>
                  <td className="pr-3 text-slate-400">{r.conditions}</td>
                  <td className="pr-3">{r.observed}</td>
                  <td className="pr-3 text-slate-400">{r.predicted}</td>
                  <td className="pr-3 font-mono">{r.margin_pct > 0 ? "+" : ""}{r.margin_pct}</td>
                  <td>
                    {r.correct
                      ? <span className="text-emerald-300">✓ correct</span>
                      : <span className="text-amber-300">✗ miss</span>}
                    {r.explanation && <div className="text-[10px] text-slate-500 mt-1 max-w-xs">{r.explanation}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

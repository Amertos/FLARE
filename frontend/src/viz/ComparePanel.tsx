import { useEffect, useMemo, useState } from "react";
import { api, type AtmosphereParams, type FlameResponse, type MissionsResponse } from "../api";

/**
 * Scenario A vs Scenario B compare.
 *
 * A is the CURRENT console state (whatever the sliders say, evaluated live by
 * /api/flame); B is a mission preset fully evaluated by /api/missions — which
 * also ships its 1g ground twin. The only numbers shown are engine outputs:
 * the margins, the effective boundaries, and the twin delta. A µg-vs-1g A/B on
 * the same parameters IS the published crossover, rendered as a delta.
 */
export default function ComparePanel({
  atm,
  flame,
}: {
  atm: AtmosphereParams;
  flame: FlameResponse;
}) {
  const [missions, setMissions] = useState<MissionsResponse | null>(null);
  const [bId, setBId] = useState<string>("gateway-orbital");

  useEffect(() => {
    let alive = true;
    api.missions().then((m) => { if (alive) setMissions(m); }).catch(() => {});
    return () => { alive = false; };
  }, []);

  const b = useMemo(
    () => missions?.scenarios.find((s) => s.id === bId) ?? null,
    [missions, bId],
  );

  const aMargin = flame.hazard.margin_above_loc_pct;
  const bMargin = b?.evaluation.margin_above_loc_pct ?? null;
  const tone = (v: number) => (v > 0 ? "text-red-300" : v < 0 ? "text-emerald-300" : "text-slate-300");

  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold text-slate-200">
        Compare A (this state) vs B (mission preset)
      </h2>
      <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 space-y-3">
        <label className="flex items-center gap-2 text-xs text-slate-400">
          B =
          <select value={bId} onChange={(e) => setBId(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-slate-100">
            {missions?.scenarios.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </label>

        <div className="grid grid-cols-[1fr_auto_1fr] gap-2 text-xs items-center">
          <div className="rounded border border-orange-900/60 bg-orange-950/20 px-2 py-2">
            <div className="text-[10px] uppercase tracking-wide text-slate-500">A — current state</div>
            <div className="font-mono text-slate-200 mt-1">
              {atm.pressure.toFixed(1)} psia · {atm.o2.toFixed(1)}% O₂ · {atm.gravity}
            </div>
            <div className="font-mono mt-1">
              margin <span className={tone(aMargin)}>{aMargin > 0 ? "+" : ""}{aMargin.toFixed(2)} pt</span>
            </div>
            <div className="font-mono text-slate-400 mt-0.5">
              LOC {flame.hazard.effective_loc_pct.toFixed(2)}% · {flame.fate.label}
            </div>
          </div>
          <div className="text-slate-600 font-bold">vs</div>
          <div className="rounded border border-sky-900/60 bg-sky-950/20 px-2 py-2">
            <div className="text-[10px] uppercase tracking-wide text-slate-500">B — mission preset</div>
            {b ? (
              <>
                <div className="font-mono text-slate-200 mt-1">
                  {b.pressure_psia.toFixed(1)} psia · {b.o2_pct.toFixed(1)}% O₂ · {b.gravity}
                </div>
                <div className="font-mono mt-1">
                  margin <span className={tone(bMargin!)}>{bMargin! > 0 ? "+" : ""}{bMargin!.toFixed(2)} pt</span>
                </div>
                <div className="font-mono text-slate-400 mt-0.5">
                  LOC {b.evaluation.effective_loc_pct.toFixed(2)}% · Δ margin{" "}
                  <span className={tone((bMargin! - aMargin))}>
                    {(bMargin! - aMargin) > 0 ? "+" : ""}{(bMargin! - aMargin).toFixed(2)} pt
                  </span>
                </div>
              </>
            ) : (
              <div className="text-slate-500">loading…</div>
            )}
          </div>
        </div>

        {b && (
          <div className="text-[11px] text-slate-400 space-y-1">
            <p>
              <span className="text-slate-500">µg-vs-1g drift (engine-computed): </span>
              <span className={tone(Math.abs(b.evaluation.delta_vs_1g.margin_pt) < 0.3 ? 0 : 1)}>
                {b.evaluation.delta_vs_1g.wording}
              </span>
            </p>
            <p className="text-slate-500 leading-relaxed">{b.context}</p>
            <p className="text-[10px] text-slate-600 font-mono">source: {b.provenance}</p>
          </div>
        )}
      </div>
    </section>
  );
}

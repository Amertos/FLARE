import { useEffect, useState } from "react";
import { api, type DesignSearchResponse, type DesignSearchRow } from "../api";
import { ScreenHeader, FlarePanel } from "../ui/FlarePanel";

/** Design Search — the inverse of the trade-space question.
 *
 *  The map answers "given this atmosphere, what happens". This screen asks the
 *  question a designer starts from: is there ANY atmosphere that is both
 *  breathable and below the LOC boundary, and at what pressure does that window
 *  open? Everything drawn here is /api/design-search output — the crossing is
 *  solved server-side in closed form, the rows are the same loc.py/hazard.py
 *  functions every other screen uses, and the window carries the epistemic flag
 *  of the pressure envelope it sits in.
 */

const STATUS: Record<
  DesignSearchRow["status"],
  { label: string; cls: string; title: string }
> = {
  usable_window: {
    label: "usable window",
    cls: "border-emerald-800 bg-emerald-950/40 text-emerald-300",
    title: "Breathable band below the boundary, wider than the model's uncertainty.",
  },
  nominal_window: {
    label: "nominal window",
    cls: "border-amber-800 bg-amber-950/40 text-amber-300",
    title: "A band exists but is narrower than the stated ±1.5 pt uncertainty band.",
  },
  unavoidable_spread: {
    label: "fire unavoidable",
    cls: "border-red-900 bg-red-950/40 text-red-300",
    title: "The crew's own oxygen floor is above the boundary: no mix in this row is fire-safe.",
  },
  outside_data: {
    label: "outside data",
    cls: "border-slate-700 bg-slate-900 text-slate-400",
    title: "Outside the calibrated pressure envelope: the boundary here is extrapolation.",
  },
};

/** Two curves, one crossing. The shaded band is the only region where a
 *  breathable mix also sits below the boundary; the LOC line turns dashed where
 *  it leaves the fitted pressure envelope. */
function WindowChart({ data }: { data: DesignSearchResponse }) {
  const W = 760;
  const H = 320;
  const pad = { l: 48, r: 18, t: 18, b: 34 };
  const rows = data.rows;
  const pmin = rows[0].pressure_psia;
  const pmax = rows[rows.length - 1].pressure_psia;
  const maxV = Math.max(...rows.map((r) => Math.max(r.crew_floor_o2_pct, r.loc_pct)));
  const yMax = Math.ceil(maxV / 10) * 10;
  const x = (p: number) => pad.l + ((p - pmin) / (pmax - pmin)) * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - v / yMax) * (H - pad.t - pad.b);
  const pts = (sel: (r: DesignSearchRow) => number) =>
    rows.map((r) => `${x(r.pressure_psia).toFixed(1)},${y(sel(r)).toFixed(1)}`).join(" ");

  const floorPts = pts((r) => r.crew_floor_o2_pct);

  const safe = rows.filter((r) => r.loc_pct > r.crew_floor_o2_pct);
  const safeArea = safe.length
    ? [
        ...safe.map((r) => `${x(r.pressure_psia)},${y(Math.min(r.loc_pct, r.crew_ceiling_o2_pct))}`),
        ...[...safe].reverse().map((r) => `${x(r.pressure_psia)},${y(r.crew_floor_o2_pct)}`),
      ].join(" ")
    : null;

  // The envelope edges sit INSIDE the drawn range, so the boundary has to be
  // split into consecutive runs by flag, not at the first extrapolated row:
  // a single findIndex made the whole line dashed from the left edge on.
  const segments: Array<{ dashed: boolean; pts: DesignSearchRow[] }> = [];
  for (const r of rows) {
    const dashed = r.flag === "EXTRAPOLATED";
    const last = segments[segments.length - 1];
    if (last && last.dashed === dashed) last.pts.push(r);
    else segments.push({ dashed, pts: [r] });
  }

  const cur = data.current;
  const showCurrent =
    cur != null && cur.pressure_psia >= pmin && cur.pressure_psia <= pmax;

  const xTicks: number[] = [];
  for (let p = Math.ceil(pmin); p <= pmax; p += 2) xTicks.push(p);
  const yTicks: number[] = [];
  for (let v = 0; v <= yMax; v += 10) yTicks.push(v);

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
        aria-label="Crew oxygen floor and LOC boundary versus cabin pressure, with the breathable fire-safe window shaded">
        {yTicks.map((v) => (
          <g key={`y${v}`}>
            <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} stroke="#1e293b" strokeWidth="1" />
            <text x={pad.l - 8} y={y(v) + 3} textAnchor="end" fontSize="10" fill="#64748b"
              fontFamily="'Geist Mono',monospace">{v}</text>
          </g>
        ))}
        {xTicks.map((p) => (
          <g key={`x${p}`}>
            <line x1={x(p)} x2={x(p)} y1={pad.t} y2={H - pad.b} stroke="#16202e" strokeWidth="1" />
            <text x={x(p)} y={H - pad.b + 14} textAnchor="middle" fontSize="10" fill="#64748b"
              fontFamily="'Geist Mono',monospace">{p}</text>
          </g>
        ))}

        {safeArea && <polygon points={safeArea} fill="rgba(16,185,129,0.16)" stroke="none" />}

        {showCurrent && (
          <g>
            <line x1={x(cur.pressure_psia)} x2={x(cur.pressure_psia)} y1={pad.t} y2={H - pad.b}
              stroke="#94a3b8" strokeWidth="1" strokeDasharray="3 3" />
            <circle cx={x(cur.pressure_psia)} cy={y(cur.crew_floor_o2_pct)} r="3.2" fill="#f59e0b" />
            <circle cx={x(cur.pressure_psia)} cy={y(cur.loc_pct)} r="3.2" fill="#38bdf8" />
            <text x={x(cur.pressure_psia) + 6} y={pad.t + 10} fontSize="10" fill="#94a3b8"
              fontFamily="'Geist Mono',monospace">now {cur.pressure_psia} psia</text>
          </g>
        )}

        <polyline points={floorPts} fill="none" stroke="#f59e0b" strokeWidth="2" />
        {segments.map((seg, i) => {
          if (seg.pts.length < 2) return null;
          const joined = i > 0 ? [segments[i - 1].pts[segments[i - 1].pts.length - 1], ...seg.pts] : seg.pts;
          return (
            <polyline key={`loc${i}`}
              points={joined.map((r) => `${x(r.pressure_psia)},${y(r.loc_pct)}`).join(" ")}
              fill="none" stroke="#38bdf8" strokeWidth="2"
              strokeDasharray={seg.dashed ? "5 4" : undefined}
              opacity={seg.dashed ? 0.75 : 1} />
          );
        })}

        <text x={W - pad.r} y={H - 4} textAnchor="end" fontSize="10" fill="#475569">
          cabin total pressure (psia)
        </text>
        <text x={pad.l + 4} y={pad.t - 4} fontSize="10" fill="#475569">O₂ (%)</text>
      </svg>

      <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-400">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 rounded bg-amber-500" />
          crew oxygen floor (pO₂ = {String(data.inputs.po2_min_psia)} psia)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 rounded bg-sky-400" />
          effective LOC boundary <span className="text-slate-600">— dashed = extrapolated</span>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-3 w-4 rounded-sm border border-emerald-800 bg-emerald-900/40" />
          breathable and below the boundary
        </span>
      </div>
    </div>
  );
}

function StatCard({ label, value, unit, note }: {
  label: string; value: string; unit?: string; note: string;
}) {
  return (
    <div className="panel">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 font-mono text-2xl text-slate-100">
        {value}
        {unit && <span className="ml-1 text-xs font-normal text-slate-500">{unit}</span>}
      </div>
      <div className="mt-1 text-[11px] leading-snug text-slate-500">{note}</div>
    </div>
  );
}

export default function DesignSearch({ query }: { query: string }) {
  const [data, setData] = useState<DesignSearchResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.designSearch(query)
      .then((r) => { if (alive) { setData(r); setErr(null); } })
      .catch((e) => alive && setErr(String(e)));
    return () => { alive = false; };
  }, [query]);

  if (err) return <div className="text-red-300 text-sm p-6">Failed to load design search: {err}</div>;
  if (!data) return <div className="text-slate-400 text-sm p-6">Solving the two constraints…</div>;

  const cur = data.current;
  const hasWindow = data.verdict === "window_exists";

  return (
    <div className="space-y-4 screen-enter">
      <ScreenHeader
        eyebrow="Screen 3 · The design problem"
        title="Design Search — can any atmosphere be both breathable and fire-safe?"
        lede="The map answers what an atmosphere costs. This screen asks the inverse question: for each cabin pressure, what oxygen does the crew need, is that oxygen below the boundary, and at what pressure do the two curves cross? Both constraints are loc.py rearranged — no new model, no recommendation."
      />

      <div className={`rounded-lg border px-4 py-3 ${hasWindow
        ? "border-emerald-800/70 bg-emerald-950/25"
        : "border-orange-800/70 bg-orange-950/25"}`}>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <span className="text-[11px] uppercase tracking-wide text-slate-400">
            {hasWindow ? "The window exists — and it is narrow" : "There is no window in this range"}
          </span>
          <span className="font-mono text-[11px] text-slate-500">
            {data.verdict.replace(/_/g, " ")}
          </span>
        </div>
        <p className="mt-1.5 text-sm leading-relaxed text-slate-200">{data.statement}</p>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Crossing pressure"
          value={data.crossover_psia == null ? "—" : data.crossover_psia.toFixed(2)}
          unit="psia"
          note="Below this pressure the crew's oxygen floor is above the boundary, so every breathable mix can spread fire."
        />
        <StatCard
          label="Widest calibrated window"
          value={data.best.window_pt.toFixed(2)}
          unit="O₂ pt"
          note={`At ${data.best.pressure_psia.toFixed(2)} psia, inside the ${data.best.flag.toLowerCase()} data envelope.`}
        />
        <StatCard
          label="Model uncertainty"
          value={`±${data.nominal_window_pt.toFixed(1)}`}
          unit="O₂ pt"
          note="Stated margin uncertainty of the 2-parameter fit (dossier §4.7 L3). A window narrower than this is nominal."
        />
        <StatCard
          label={cur ? `At ${cur.pressure_psia.toFixed(1)} psia` : "Current state"}
          value={cur ? (cur.shortfall_pt > 0
            ? cur.shortfall_pt.toFixed(1)
            : cur.window_pt.toFixed(2)) : "—"}
          unit={cur && cur.shortfall_pt > 0 ? "pt above" : "O₂ pt window"}
          note={cur
            ? `Crew floor ${cur.crew_floor_o2_pct.toFixed(1)}% O₂, effective LOC ${cur.loc_pct.toFixed(1)}% — ${cur.shortfall_pt > 0 ? "fire is unavoidable at any crew-safe mix" : "a breathable band sits below the boundary"}.`
            : "No state supplied."}
        />
      </div>

      <FlarePanel title="The two constraints, and where they cross"
        hint="shaded = breathable AND below the boundary">
        <WindowChart data={data} />
      </FlarePanel>

      <FlarePanel title="Pressure by pressure" hint={`${data.rows.length} rows · solved by the engine`}>
        <div className="max-h-80 overflow-auto">
          <table className="w-full text-[11px]">
            <thead className="sticky top-0 bg-slate-950/95">
              <tr className="text-slate-500 text-left">
                <th className="py-1 pr-2 font-normal">P (psia)</th>
                <th className="py-1 pr-2 font-normal text-right">crew floor %</th>
                <th className="py-1 pr-2 font-normal text-right">effective LOC %</th>
                <th className="py-1 pr-2 font-normal text-right">window</th>
                <th className="py-1 pr-2 font-normal text-right">ignition at floor</th>
                <th className="py-1 pr-2 font-normal">boundary</th>
                <th className="py-1 font-normal">status</th>
              </tr>
            </thead>
            <tbody className="font-mono text-slate-300">
              {data.rows.map((r) => {
                const st = STATUS[r.status];
                return (
                  <tr key={r.pressure_psia} className="border-t border-slate-800/60">
                    <td className="py-1 pr-2">{r.pressure_psia.toFixed(2)}</td>
                    <td className="py-1 pr-2 text-right text-amber-300/90">{r.crew_floor_o2_pct.toFixed(1)}</td>
                    <td className="py-1 pr-2 text-right text-sky-300/90">{r.loc_pct.toFixed(1)}</td>
                    <td className={`py-1 pr-2 text-right ${r.window_pt > 0 ? "text-emerald-300" : "text-red-300/80"}`}>
                      {r.window_pt > 0 ? `+${r.window_pt.toFixed(2)}` : `${(-r.shortfall_pt).toFixed(1)}`}
                    </td>
                    <td className="py-1 pr-2 text-right text-slate-400">{r.ignition_at_floor.toFixed(1)}</td>
                    <td className={`py-1 pr-2 ${r.flag === "INTERPOLATED" ? "text-slate-500" : "text-slate-600"}`}>
                      {r.flag === "INTERPOLATED" ? "interp" : "extrap"}
                    </td>
                    <td className="py-1">
                      <span className={`rounded border px-1.5 py-0.5 text-[10px] ${st.cls}`} title={st.title}>
                        {st.label}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-[11px] text-slate-500">
          Window is negative where the crew floor sits above the boundary; the number shown is how many
          O₂ points the crew needs beyond what the atmosphere can sustain. Ignition at floor is the
          engine's ignition index for the leanest breathable mix — it never reaches 0 because the index
          has a pilot-source floor.
        </p>
      </FlarePanel>

      <FlarePanel title="Method" hint="what this search is and is not">
        <ul className="text-xs text-slate-400 space-y-1.5 list-disc pl-4">
          {data.notes.map((n, i) => <li key={i}>{n}</li>)}
        </ul>
      </FlarePanel>
    </div>
  );
}

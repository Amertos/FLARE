import { useEffect, useState } from "react";
import { api, type CountermovesLever, type CountermovesResponse } from "../api";
import { ScreenHeader, FlarePanel } from "../ui/FlarePanel";

/** The Countermoves screen: ranked, engine-computed fire-safety levers for
 *  the atmosphere on the address bar.
 *
 *  The screen renders ONLY what /api/countermoves already contains: every
 *  before/after figure is the engine's own output, the ranking travels with
 *  the payload (`ranked_ids`), and each lever carries its epistemic label —
 *  bounded-fit, cited-behaviour or model-construct — verbatim. Levers the
 *  model does not support in this regime are shown as not-applicable WITH the
 *  reason, which is the honest alternative to rendering a zero-effect row as
 *  a recommendation.
 */

const GLYPHS: Record<string, string> = {
  cool_cabin: "❄️",
  material_substitution: "🧱",
  reduce_flow: "🌀",
  o2_to_crew_floor: "⬇️",
};

function DeltaChip({ label, value, better }: {
  label: string; value: number; better: boolean;
}) {
  if (value === 0) {
    return (
      <span className="inline-flex items-center gap-1 rounded border border-slate-700 bg-slate-900 px-1.5 py-0.5 font-mono text-[10px] text-slate-500"
        title="No engine-modelled effect on this quantity">
        {label}
      </span>
    );
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10px] ${better
      ? "border-emerald-800 bg-emerald-950/40 text-emerald-300"
      : "border-slate-700 bg-slate-900 text-slate-400"}`}>
      {value > 0 ? "+" : ""}{value.toFixed(1)} pt {label}
    </span>
  );
}

function LeverCard({ lever, rank }: { lever: CountermovesLever; rank: number | null }) {
  if (!lever.applicable) {
    return (
      <div className="panel opacity-70">
        <div className="flex items-center gap-2 mb-2">
          <span className="corner-mark shrink-0" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-slate-300">{lever.title}</h3>
          <span className="ml-auto rounded border border-slate-700 bg-slate-900 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
            not applicable here
          </span>
        </div>
        <p className="text-xs text-slate-400">{lever.action}</p>
        <p className="mt-1.5 text-[11px] text-slate-500">{lever.note}</p>
      </div>
    );
  }
  const { before, after, delta } = lever;
  return (
    <div className="panel relative">
      {rank != null && (
        <span className="absolute -top-2 -left-2 flex h-6 w-6 items-center justify-center rounded-full border border-orange-800 bg-orange-950 font-mono text-[11px] text-orange-300"
          title="Rank of the applicable levers, by engine-predicted drop in the ignition index">
          {rank + 1}
        </span>
      )}
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 mb-1.5">
        <span className="text-base" aria-hidden="true">{GLYPHS[lever.id] ?? "🎚️"}</span>
        <h3 className="text-sm font-semibold text-slate-100">{lever.title}</h3>
      </div>
      <p className="text-xs text-slate-300">{lever.action}</p>

      <div className="mt-2.5 flex flex-wrap gap-1.5">
        <DeltaChip label="ignition" value={delta.ignition} better={delta.ignition < 0} />
        <DeltaChip label="spread" value={delta.spread} better={delta.spread < 0} />
        <DeltaChip label="margin above LOC" value={delta.margin_above_loc_pct} better={delta.margin_above_loc_pct < 0} />
      </div>

      {(() => {
        const rows: Array<[string, number, number, string]> = [
          ["Ignition", before.ignition, after.ignition, "of 100"],
          ["Spread", before.spread, after.spread, "of 100"],
          ["Margin above LOC", before.margin_above_loc_pct, after.margin_above_loc_pct, "pts of O₂"],
          ["Crew pO₂", before.crew.po2_psia, after.crew.po2_psia, "psia"],
        ];
        return (
          <table className="mt-2.5 w-full text-[11px]">
            <thead>
              <tr className="text-slate-600 text-left">
                <th className="py-0.5 pr-2 font-normal">Quantity</th>
                <th className="py-0.5 pr-2 font-normal text-right">before</th>
                <th className="py-0.5 font-normal text-right">after lever</th>
              </tr>
            </thead>
            <tbody className="font-mono text-slate-400">
              {rows.map((r) => (
                <tr key={r[0]} className="border-t border-slate-800/50">
                  <td className="py-0.5 pr-2 text-slate-500">{r[0]}</td>
                  <td className="py-0.5 pr-2 text-right">{r[1].toFixed(r[0].startsWith("Crew") ? 2 : 1)}</td>
                  <td className={`py-0.5 text-right ${r[2] < r[1] ? "text-emerald-300" : ""}`}>{r[2].toFixed(r[0].startsWith("Crew") ? 2 : 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        );
      })()}

      <p className="mt-2 text-[11px] text-slate-500 italic">{lever.note}</p>
      <p className="mt-1 text-[10px] leading-snug text-slate-600">{lever.evidence_label}</p>
    </div>
  );
}

export default function Countermoves({ query }: { query: string }) {
  const [data, setData] = useState<CountermovesResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.countermoves(query)
      .then((r) => { if (alive) { setData(r); setErr(null); } })
      .catch((e) => alive && setErr(String(e)));
    return () => { alive = false; };
  }, [query]);

  if (err) return <div className="text-red-300 text-sm p-6">Failed to load countermoves: {err}</div>;
  if (!data) return <div className="text-slate-400 text-sm p-6">Evaluating levers…</div>;

  const rankOf = (id: string) => data.ranked_ids.indexOf(id);
  const b = data.baseline;

  return (
    <div className="space-y-4 screen-enter">
      <ScreenHeader
        eyebrow="Screen 2 · The levers"
        title="Countermoves — how to lower the fire risk"
        lede="Four planning levers, computed by the same engine as the trade-space map: each reports its own before/after hazard vector, ranked by predicted drop in the ignition index. What the model cannot support in this regime is stated as not-applicable, not rendered as a recommendation."
      />

      <FlarePanel
        title="Baseline — the state the levers act on"
        hint="engine vector for the atmosphere on the address bar"
      >
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-center">
          {([
            ["Ignition", b.ignition],
            ["Spread", b.spread],
            ["Persistence", b.persistence],
            ["Heat release", b.heat_release],
            ["Margin above LOC", b.margin_above_loc_pct],
          ] as Array<[string, number]>).map(([label, v]) => (
            <div key={label} className="rounded border border-slate-800 bg-slate-900/60 py-2">
              <div className="font-mono text-lg num">{v.toFixed(1)}</div>
              <div className="text-[10px] text-slate-500">{label}</div>
            </div>
          ))}
        </div>
        <div className="mt-2 text-[11px] text-slate-500">
          Crew pO₂ {b.crew.po2_psia.toFixed(2)} psia ({b.crew.normoxia_pct.toFixed(0)}% of sea-level
          normoxia) — {b.crew.crew_safe ? "inside the crew band" : "outside the crew band"}
          (the band is a model construct, limitation L6).
        </div>
      </FlarePanel>

      <div className="grid md:grid-cols-2 gap-4">
        {data.levers.map((lever) => (
          <LeverCard key={lever.id} lever={lever} rank={rankOf(lever.id)} />
        ))}
      </div>

      <FlarePanel title="Method" hint="what this ranking is and is not">
        <ul className="text-xs text-slate-400 space-y-1.5 list-disc pl-4">
          {data.notes.map((n, i) => <li key={i}>{n}</li>)}
        </ul>
      </FlarePanel>
    </div>
  );
}

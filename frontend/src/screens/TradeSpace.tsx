import type { AtmosphereParams, ParetoResponse, ScenarioResponse, TradeSpaceResponse } from "../api";
import { api } from "../api";
import { useCallback, useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { FlarePanel, ScreenHeader } from "../ui/FlarePanel";

const LABEL_STYLES: Record<string, string> = {
  OBSERVED: "bg-emerald-900/60 text-emerald-300 border-emerald-700",
  INTERPOLATED: "bg-amber-900/60 text-amber-300 border-amber-700",
  EXTRAPOLATED: "bg-orange-900/60 text-orange-300 border-orange-700",
  INSUFFICIENT: "bg-red-900/60 text-red-300 border-red-700",
};

// KPI cards must not let a long label or a wide figure bend their neighbours'
// row; the value and its label clip instead of pushing the grid apart.
const KPI_VALUE_CLS = "kpi-value text-lg sm:text-xl max-w-full";
const KPI_LABEL_CLS = "text-[10px] uppercase tracking-wide text-slate-500 truncate"

function Bar({ label, value }: { label: string; value: number }) {
  const color = value >= 66 ? "bg-red-500" : value >= 33 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-32 text-slate-400">{label}</span>
      <div className="flex-1 h-2.5 bg-slate-800 rounded overflow-hidden">
        <div className={`h-full ${color} rounded`} style={{ width: `${Math.min(100, value)}%` }} />
      </div>
      <span className="w-10 text-right font-mono text-slate-200">{value.toFixed(0)}</span>
    </div>
  );
}

function HazardMap({ trade, o2Sel, pSel, onPick }: {
  trade: TradeSpaceResponse; o2Sel: number; pSel: number; onPick: (p: number, o2: number) => void;
}) {
  const ref = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const W = 720, H = 480, M = { t: 14, r: 14, b: 44, l: 56 };
    const svg = d3.select(ref.current);
    svg.selectAll("*").remove();
    const ps = trade.p_psia, o2s = trade.o2_pct;
    const x = d3.scaleLinear().domain(d3.extent(ps) as [number, number]).range([M.l, W - M.r]);
    const y = d3.scaleLinear().domain(d3.extent(o2s) as [number, number]).range([H - M.b, M.t]);
    const iw = (W - M.l - M.r) / ps.length, ih = (H - M.t - M.b) / o2s.length;
    const heat = d3.scaleSequential<string>(d3.interpolateRdYlGn).domain([90, 0]).unknown("#1e293b");

    // crew-safe band (pO2 in [2.4, 3.4] psia)
    const o2For = (p: number, po2: number) => (po2 / p) * 100;
    const bandTop = o2For(pSel, trade.crew_band.po2_max_psia);
    const bandBot = o2For(pSel, trade.crew_band.po2_min_psia);
    svg.append("rect").attr("x", M.l).attr("y", y(Math.min(bandTop, trade.o2_pct[trade.o2_pct.length - 1])))
      .attr("width", W - M.l - M.r)
      .attr("height", Math.max(0, y(Math.max(0, bandBot)) - y(Math.min(bandTop, trade.o2_pct[trade.o2_pct.length - 1]))))
      .attr("fill", "#38bdf8").attr("opacity", 0.10);

    // heat cells (ignition tendency)
    ps.forEach((p, i) => o2s.forEach((o, j) => {
      svg.append("rect").attr("x", x(p) - iw / 2).attr("y", y(o) - ih / 2)
        .attr("width", iw).attr("height", ih)
        .attr("fill", heat(trade.grid[i][j].ignition));
    }));

    // Extrapolation regions: outside the experimental coverage envelope on the
    // pressure axis no pixel is coloured. The area is hatched and labelled
    // instead, and the hatch is drawn OVER the heat cells so colour can never
    // imply evidence that does not exist (dossier §4.7 L2).
    const defs = svg.append("defs");
    const hatch = defs.append("pattern")
      .attr("id", "flare-extrapolated")
      .attr("width", 7).attr("height", 7)
      .attr("patternUnits", "userSpaceOnUse")
      .attr("patternTransform", "rotate(45)");
    hatch.append("rect").attr("width", 7).attr("height", 7)
      .attr("fill", "#020617").attr("opacity", 0.82);
    hatch.append("line").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 7)
      .attr("stroke", "#f59e0b").attr("stroke-width", 1.6).attr("opacity", 0.55);

    const kpaToPsia = (kpa: number) => kpa / 6.89476;
    const plotX0 = M.l, plotX1 = W - M.r, plotH = H - M.t - M.b;
    const clampX = (v: number) => Math.max(plotX0, Math.min(plotX1, v));
    const envLo = clampX(x(kpaToPsia(trade.p_envelope_kpa[0])));
    const envHi = clampX(x(kpaToPsia(trade.p_envelope_kpa[1])));
    const regions: Array<{ x0: number; w: number }> = [];
    if (envLo > plotX0) regions.push({ x0: plotX0, w: envLo - plotX0 });
    if (envHi < plotX1) regions.push({ x0: envHi, w: plotX1 - envHi });
    regions.forEach((r) => {
      svg.append("rect").attr("x", r.x0).attr("y", M.t)
        .attr("width", r.w).attr("height", plotH)
        .attr("fill", "url(#flare-extrapolated)");
    });
    regions.forEach((r) => {
      svg.append("text")
        .attr("x", r.x0 + r.w / 2).attr("y", M.t + plotH / 2)
        .attr("fill", "#fbbf24").attr("font-size", 10)
        .attr("text-anchor", "middle")
        .attr("transform", `rotate(-90 ${r.x0 + r.w / 2} ${M.t + plotH / 2})`)
        .text("EXTRAPOLATED");
    });

    // LOC boundary (only where covered)
    const line = d3.line<{ p_psia: number; loc_pct: number | null }>()
      .x((d) => x(d.p_psia)).y((d) => (d.loc_pct != null ? y(d.loc_pct) : NaN))
      .defined((d) => d.loc_pct != null);
    svg.append("path").datum(trade.loc_boundary)
      .attr("d", line).attr("fill", "none")
      .attr("stroke", "#f8fafc").attr("stroke-width", 2.5).attr("stroke-dasharray", "1 0");
    svg.append("text").attr("x", M.l + 8).attr("y", y(24)).attr("fill", "#f8fafc")
      .attr("font-size", 11).text("LOC boundary — fire above, no sustained spread below");

    // selected marker
    svg.append("circle").attr("cx", x(pSel)).attr("cy", y(o2Sel)).attr("r", 6)
      .attr("fill", "none").attr("stroke", "#facc15").attr("stroke-width", 2.5);

    // axes
    svg.append("g").attr("transform", `translate(0,${H - M.b})`)
      .call(d3.axisBottom(x).tickFormat((d) => `${d}`));
    svg.append("g").attr("transform", `translate(${M.l},0)`)
      .call(d3.axisLeft(y).tickFormat((d) => `${d}`));
    svg.append("text").attr("x", W / 2).attr("y", H - 6).attr("fill", "#94a3b8")
      .attr("text-anchor", "middle").attr("font-size", 12).text("Total pressure (psia)");
    svg.append("text").attr("x", 14).attr("y", H / 2).attr("fill", "#94a3b8")
      .attr("text-anchor", "middle").attr("font-size", 12)
      .attr("transform", `rotate(-90 14 ${H / 2})`).text("O₂ concentration (%)");

    svg.on("click", (event: MouseEvent) => {
      const [mx, my] = d3.pointer(event);
      const p = x.invert(mx), o2 = y.invert(my);
      const cp = ps.reduce((a, b) => (Math.abs(b - p) < Math.abs(a - p) ? b : a));
      const co = o2s.reduce((a, b) => (Math.abs(b - o2) < Math.abs(a - o2) ? b : a));
      onPick(cp, co);
    });
  }, [trade, o2Sel, pSel, onPick]);

  return <svg ref={ref} viewBox="0 0 720 480" className="w-full" role="img"
    aria-label="Trade-space map of ignition tendency against total pressure and oxygen concentration, with the limiting-oxygen-concentration boundary and a hatched region outside NASA data coverage" />;
}

/** Fire-safety vs EVA-benefit frontier. FLARE never declares a winner: the
 *  slider moves which candidate the scalar ranking favours, and the frontier
 *  shows the set that is not dominated by any other. */
function ParetoPanel({ atm }: { atm: AtmosphereParams }) {
  const [weight, setWeight] = useState(0.5);
  const [data, setData] = useState<ParetoResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.pareto(
      `fire_weight=${weight}&gravity=${atm.gravity}&flow_ms=${atm.flow}` +
        `&temperature_c=${atm.temperature}&material_class=${atm.material}`,
    )
      .then((r) => alive && (setData(r), setErr(null)))
      .catch((e) => alive && setErr(String(e)));
    return () => { alive = false; };
  }, [weight, atm.gravity, atm.flow, atm.temperature, atm.material]);

  const frontCount = data?.candidates.filter((c) => c.on_frontier).length ?? 0;

  return (
    <FlarePanel
      title="Candidate atmospheres — fire safety vs EVA benefit"
      hint={`${frontCount} on the frontier`}
    >
      <p className="text-[11px] text-slate-400 mb-3">
        Six candidate atmospheres are scored on two axes: fire risk (lower is better, from the
        ignition component) and EVA benefit (higher is better — lower cabin pressure means less
        prebreathe time). The frontier holds the candidates nothing else beats on both axes at once.
        <span className="text-slate-300"> FLARE does not pick a winner</span> — move the weight and
        watch the ranking change hands.
      </p>

      <label className="flex items-center gap-3 text-xs text-slate-300 mb-3">
        <span className="w-40 shrink-0">Weight on fire safety</span>
        <input type="range" min={0} max={1} step={0.05} value={weight}
          aria-label="Weight placed on fire safety versus EVA benefit"
          onChange={(e) => setWeight(+e.target.value)} className="flex-1 accent-orange-500" />
        <span className="font-mono w-12 text-right">{weight.toFixed(2)}</span>
      </label>

      {err && <div className="text-red-300 text-xs">Pareto frontier unavailable ({err}).</div>}

      {data && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-500 text-left">
                <th className="py-1 pr-3 font-medium">Candidate</th>
                <th className="pr-3 font-medium">Atmosphere</th>
                <th className="pr-3 font-medium">Fire risk</th>
                <th className="pr-3 font-medium">EVA benefit</th>
                <th className="pr-3 font-medium">pO₂</th>
                <th className="pr-3 font-medium">Crew-safe</th>
                <th className="pr-3 font-medium">Frontier</th>
                <th className="font-medium">Score (w={weight.toFixed(2)})</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {data.candidates.map((c) => (
                <tr key={c.id}
                  className={`border-t border-slate-800 ${c.id === data.recommended ? "bg-orange-950/30" : ""}`}>
                  <td className="py-1 pr-3">
                    {c.id}
                    {c.id === data.recommended && (
                      <span className="ml-1 text-[9px] font-sans text-orange-300">top of ranking</span>
                    )}
                  </td>
                  <td className="pr-3">{c.p} psia / {c.o2}%</td>
                  <td className="pr-3">{c.fire_risk.toFixed(2)}</td>
                  <td className="pr-3">{c.eva.toFixed(2)}</td>
                  <td className="pr-3">{c.normoxia_pct.toFixed(0)}%</td>
                  <td className="pr-3">
                    {c.crew_safe
                      ? <span className="text-emerald-300">✓</span>
                      : <span className="text-slate-500">—</span>}
                  </td>
                  <td className="pr-3">
                    {c.on_frontier
                      ? <span className="text-[9px] font-sans text-sky-300 border border-sky-800 rounded px-1">non-dominated</span>
                      : <span className="text-[9px] font-sans text-slate-500">dominated</span>}
                  </td>
                  <td>{c.weighted_score.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[11px] text-slate-500 mt-2">
            Fire risk is the ignition component divided by 100 and is a <em>relative</em> comparison
            between candidates, not an absolute risk; the EVA axis is a stated model construct of
            this project (dossier limitations L4, L6).
          </p>
        </div>
      )}
    </FlarePanel>
  );
}

export default function TradeSpace({ scenario, trade, atm, pressure, o2, onPick }: {
  scenario: ScenarioResponse | null;
  trade: TradeSpaceResponse | null;
  atm: AtmosphereParams;
  pressure: number; o2: number;
  onPick?: (p: number, o2: number) => void;
}) {
  const dispatchPick = useCallback((p: number, o2v: number) => {
    window.dispatchEvent(new CustomEvent("flare-pick", { detail: { p, o2: o2v } }));
  }, []);

  if (!scenario || !trade) return <div className="text-slate-400 text-sm p-6">Loading engine…</div>;
  const h = scenario.hazard;
  const marginTone = h.margin_above_loc_pct > 0 ? "text-[var(--flare-alarm)]"
    : "text-[var(--flare-safe)]";
  const coverageTone = scenario.coverage_pct >= 66 ? "text-[var(--flare-safe)]"
    : scenario.coverage_pct >= 40 ? "text-[var(--flare-warn)]" : "text-[var(--flare-alarm)]";

  return (
    <div className="screen-enter">
      <ScreenHeader
        eyebrow="Screen 1 · The decision"
        title="Trade Space — Pressure × O₂"
        lede="The full design map: ignition tendency across pressure and oxygen, the limiting-oxygen-concentration boundary, and the frontier of candidates nothing dominates. Click any cell to move the console there."
      />

      {/* KPI summary row — the five numbers a reviewer quotes, engine-fed live. */}
      <div className="kpi-row mt-2" aria-label="Engineering summary for the selected atmosphere">
        <div className="kpi min-w-0">
          <div className={KPI_LABEL_CLS}>margin above LOC</div>
          <div className={`${KPI_VALUE_CLS} ${marginTone}`}>
            {h.margin_above_loc_pct > 0 ? "+" : ""}{h.margin_above_loc_pct.toFixed(2)} pt
          </div>
          <div className="text-[10px] text-slate-500">boundary {h.effective_loc_pct.toFixed(2)}% O₂</div>
        </div>
        <div className="kpi min-w-0">
          <div className={KPI_LABEL_CLS}>crew pO₂</div>
          {/* The unit lives in the sub-line, not the value: a number + unit in
              one nowrap line can clip by a sub-pixel on narrow cards, and a
              clipped figure is worse than a unit on its own line. */}
          <div className={KPI_VALUE_CLS}>{h.crew.po2_psia.toFixed(2)}</div>
          <div className="text-[10px] text-slate-500">psia · {h.crew.normoxia_pct.toFixed(1)}% of normoxia</div>
        </div>
        <div className="kpi min-w-0">
          <div className={KPI_LABEL_CLS}>evidence coverage</div>
          <div className={`${KPI_VALUE_CLS} ${coverageTone}`}>{scenario.coverage_pct.toFixed(1)}%</div>
          <div className="text-[10px] text-slate-500">label {scenario.evidence_label}</div>
        </div>
        <div className="kpi min-w-0">
          <div className={KPI_LABEL_CLS}>LOC status</div>
          {/* The flag is payload, not decoration: OBSERVED vs EXTRAPOLATED
              changes how every other number reads. It renders as the same chip
              style the hazard panel uses, which is dimensioned for these exact
              12-character strings and never clips them. */}
          <div className="mt-1">
            <span className={`text-[10px] px-2 py-0.5 rounded border font-mono inline-block max-w-full truncate ${LABEL_STYLES[scenario.evidence_label] ?? ""}`}>
              {scenario.loc.flag}
            </span>
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">base {scenario.loc.base_pct.toFixed(2)}%</div>
        </div>
        <div className="kpi min-w-0">
          <div className={KPI_LABEL_CLS}>crew-safe band</div>
          <div className={KPI_VALUE_CLS}>
            {h.crew.crew_safe
              ? <span className="text-[var(--flare-safe)]">inside</span>
              : <span className="text-[var(--flare-warn)]">outside</span>}
          </div>
          <div className="text-[10px] text-slate-500">pO₂ ∈ [2.4, 3.4] psia (planning construct, L6)</div>
        </div>
      </div>

      <div className="grid lg:grid-cols-[1fr_340px] gap-4">
        <FlarePanel
          title="Ignition tendency map"
          hint="white line = LOC boundary · click to move the console"
        >
          <HazardMap trade={trade} o2Sel={o2} pSel={pressure} onPick={onPick ?? dispatchPick} />
          <div className="flex flex-wrap gap-4 mt-2 text-[11px] text-slate-400">
            <span><span className="inline-block w-3 h-3 bg-red-500 align-middle mr-1 rounded-sm" />high ignition tendency</span>
            <span><span className="inline-block w-3 h-3 bg-emerald-500 align-middle mr-1 rounded-sm" />low</span>
            <span><span className="inline-block w-3 h-3 bg-sky-400/30 align-middle mr-1 rounded-sm" />crew-safe pO₂ band</span>
            <span>— LOC flammability boundary (rendered only within data coverage)</span>
            <span>
              <span className="inline-block w-3 h-3 align-middle mr-1 rounded-sm border border-amber-600 bg-slate-950"
                style={{ backgroundImage: "repeating-linear-gradient(45deg, #f59e0b55 0 1px, transparent 1px 5px)" }} />
              outside NASA data coverage — hatched, never coloured
            </span>
          </div>
        </FlarePanel>

        <div className="space-y-4">
          <FlarePanel
            title="Fire Hazard Vector"
            headerExtra={
              <span className={`text-[10px] px-2 py-0.5 rounded border font-mono ${LABEL_STYLES[scenario.evidence_label] ?? ""}`}>
                {scenario.evidence_label}
              </span>
            }
          >
            <div className="space-y-1.5">
              <Bar label="Ignition" value={h.ignition} />
              <Bar label="Spread" value={h.spread} />
              <Bar label="Persistence" value={h.persistence} />
              <Bar label="Heat release" value={h.heat_release} />
              <Bar label="Extinction margin" value={h.extinction_margin} />
            </div>
            <div className="mt-3 pt-3 border-t border-slate-800 text-xs space-y-1">
              <div className="flex justify-between"><span className="text-slate-400">Effective LOC boundary</span><span className="font-mono">{h.effective_loc_pct}% O₂</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Margin above boundary</span><span className={`font-mono ${h.margin_above_loc_pct >= 0 ? "text-red-300" : "text-emerald-300"}`}>{h.margin_above_loc_pct > 0 ? "+" : ""}{h.margin_above_loc_pct} pts</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Crew pO₂</span><span className="font-mono">{h.crew.po2_psia} psia ({h.crew.normoxia_pct}% normoxia)</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Evidence coverage</span><span className="font-mono">{scenario.coverage_pct}%</span></div>
            </div>
            <p className="text-[10px] text-slate-500 mt-2">
              Persistence and heat release are derived from spread by construction — they are not
              independent measurements (dossier §4.6, limitation L4).
            </p>
          </FlarePanel>

          <FlarePanel title="Closest controlled experiments">
            <ul className="space-y-2 text-xs">
              {scenario.relevant_experiments
                .filter((e) => e.record_kind === "experiment")
                .slice(0, 5)
                .map((e) => (
                  <li key={e.experiment_id} className="flex items-center gap-2 rounded border border-slate-800/70 px-2 py-1.5 hover:bg-slate-900/60">
                    <a href={e.source_url} target="_blank" rel="noreferrer" title={`Open source: ${e.source_type} ${e.source_id}`}
                      className="text-sky-300 hover:underline font-mono">{e.experiment_id}</a>
                    <span className="text-slate-500 flex-1 truncate">{e.mission}</span>
                    <span className={`text-[10px] px-1.5 rounded border ${e.verdict === "spread" ? "border-red-800 text-red-300" : e.verdict === "extinguish" ? "border-emerald-800 text-emerald-300" : "border-slate-700 text-slate-400"}`}>{e.verdict}</span>
                    <span className="font-mono text-slate-500">{((e.similarity ?? 0) * 100).toFixed(0)}%</span>
                  </li>
                ))}
            </ul>
            <p className="text-[10px] text-slate-500 mt-2">
              Similarity is a weighted condition distance (P 0.35 / O₂ 0.35 / gravity 0.20 / material 0.10), a ranking — not a probability.
            </p>
          </FlarePanel>
        </div>
      </div>

      <ParetoPanel atm={atm} />
    </div>
  );
}

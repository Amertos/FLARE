import type { ScenarioResponse, TradeSpaceResponse } from "../api";
import { useEffect, useRef } from "react";
import * as d3 from "d3";

const LABEL_STYLES: Record<string, string> = {
  OBSERVED: "bg-emerald-900/60 text-emerald-300 border-emerald-700",
  INTERPOLATED: "bg-amber-900/60 text-amber-300 border-amber-700",
  EXTRAPOLATED: "bg-orange-900/60 text-orange-300 border-orange-700",
  INSUFFICIENT: "bg-red-900/60 text-red-300 border-red-700",
};

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
    const bandTop = o2For(pSel, 3.4), bandBot = o2For(pSel, 2.4);
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

  return <svg ref={ref} viewBox="0 0 720 480" className="w-full" />;
}

export default function TradeSpace({ scenario, trade, mission, pressure, o2, onPick }: {
  scenario: ScenarioResponse | null;
  trade: TradeSpaceResponse | null;
  mission: { label: string; gravity: string };
  pressure: number; o2: number;
  onPick?: (p: number, o2: number) => void;
}) {
  void mission;
  if (!scenario || !trade) return <div className="text-slate-400 text-sm p-6">Loading engine…</div>;
  const h = scenario.hazard;
  return (
    <div className="grid lg:grid-cols-[1fr_340px] gap-4">
      <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
        <div className="flex items-baseline justify-between mb-2">
          <h2 className="font-semibold">Trade Space — Pressure × O₂ (ignition tendency)</h2>
          <span className="text-[11px] text-slate-400">click the map to explore · white line = LOC boundary</span>
        </div>
        <HazardMap trade={trade} o2Sel={o2} pSel={pressure}
          onPick={onPick ?? ((p, o2v) => window.dispatchEvent(new CustomEvent("flare-pick", { detail: { p, o2: o2v } })))} />
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
      </div>

      <div className="space-y-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-sm">Fire Hazard Vector</h3>
            <span className={`text-[10px] px-2 py-0.5 rounded border font-mono ${LABEL_STYLES[scenario.evidence_label] ?? ""}`}>
              {scenario.evidence_label}
            </span>
          </div>
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
        </div>

        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
          <h3 className="font-semibold text-sm mb-2">Closest experiments</h3>
          <ul className="space-y-1.5 text-xs">
            {scenario.relevant_experiments.slice(0, 5).map((e: { experiment_id: string; mission: string; verdict: string; similarity?: number; source_url: string }) => (
              <li key={e.experiment_id} className="flex items-center justify-between gap-2">
                <a href={e.source_url} target="_blank" rel="noreferrer"
                  className="text-sky-300 hover:underline font-mono">{e.experiment_id}</a>
                <span className="text-slate-400">{e.verdict}</span>
                <span className="font-mono text-slate-500">{((e.similarity ?? 0) * 100).toFixed(0)}%</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

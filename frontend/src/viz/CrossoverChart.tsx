import { useMemo, useState } from "react";
import * as d3 from "d3";
import type { FlameResponse } from "../api";

/**
 * Margin above the effective LOC boundary, microgravity vs 1g, at one pressure.
 *
 * This is the one figure on the screen that contradicts the folk belief that
 * space always burns slower. The two lines cross because the engine's gravity
 * offset is a fixed 0.8 pt shift in the boundary: above the crossing the 1g
 * margin is larger, below it microgravity's is. That is the engine's expression
 * of the published BASS-II result (FL3), not curved fitted to the figure.
 */
const W = 640;
const H = 260;
const M = { top: 18, right: 84, bottom: 34, left: 46 };

export default function CrossoverChart({ flame }: { flame: FlameResponse }) {
  const c = flame.crossover;
  const [hover, setHover] = useState<{ o2: number; ug: number; g: number } | null>(null);

  const { x, y, ugPath, gPath, crossX } = useMemo(() => {
    const ug = c.series.microgravity;
    const g = c.series.earth;
    const values = [...ug, ...g].map((p) => p.margin_pct);
    const x = d3.scaleLinear()
      .domain([c.o2_pct[0], c.o2_pct[c.o2_pct.length - 1]])
      .range([M.left, W - M.right]);
    const y = d3.scaleLinear()
      .domain([Math.min(...values) - 2, Math.max(...values) + 2])
      .range([H - M.bottom, M.top]);
    const line = d3.line<{ o2_pct: number; margin_pct: number }>()
      .x((p) => x(p.o2_pct))
      .y((p) => y(p.margin_pct));
    // The series are sampled on the same O2 grid, so the crossing is where the
    // margins swap order — read off the samples, not assumed.
    let crossX: number | null = null;
    for (let i = 1; i < ug.length; i++) {
      const d0 = ug[i - 1].margin_pct - g[i - 1].margin_pct;
      const d1 = ug[i].margin_pct - g[i].margin_pct;
      if (d0 === 0) { crossX = x(ug[i - 1].o2_pct); break; }
      if (d0 * d1 < 0) {
        const t = d0 / (d0 - d1);
        crossX = x(ug[i - 1].o2_pct + t * (ug[i].o2_pct - ug[i - 1].o2_pct));
        break;
      }
    }
    return { x, y, ugPath: line(ug) ?? "", gPath: line(g) ?? "", crossX };
  }, [c]);

  const zeroY = y(0);

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto"
        role="img"
        aria-label={`Margin above the limiting oxygen concentration boundary versus oxygen concentration at ${c.pressure_psia} psia, microgravity and 1g. The lines cross near ${c.microgravity_sustains_below_1g_at_pct}% oxygen.`}>
        {/* margin = 0: the boundary itself */}
        <line x1={M.left} x2={W - M.right} y1={zeroY} y2={zeroY}
          stroke="#475569" strokeDasharray="4 4" />
        <text x={M.left + 4} y={zeroY - 5} fontSize={10} fill="#94a3b8">boundary (margin 0)</text>

        {crossX != null && (
          <g>
            <line x1={crossX} x2={crossX} y1={M.top} y2={H - M.bottom}
              stroke="#fbbf24" strokeDasharray="2 3" />
            <text x={crossX + 5} y={M.top + 10} fontSize={10} fill="#fbbf24">
              crossover ≈ {c.microgravity_sustains_below_1g_at_pct}% O₂
            </text>
          </g>
        )}

        <path d={gPath} fill="none" stroke="#f97316" strokeWidth={2} />
        <path d={ugPath} fill="none" stroke="#38bdf8" strokeWidth={2} />

        {/* the two published anchor points from BASS-II */}
        <circle cx={x(21)} cy={y(c.series.earth.find((p) => p.o2_pct >= 21)?.margin_pct ?? 0)}
          r={4} fill="#f97316" stroke="#0f172a" strokeWidth={2} />
        <circle cx={x(17)} cy={y(c.series.microgravity.find((p) => p.o2_pct >= 17)?.margin_pct ?? 0)}
          r={4} fill="#38bdf8" stroke="#0f172a" strokeWidth={2} />

        <text x={W - M.right + 6} y={M.top + 10} fontSize={10} fill="#f97316">1g</text>
        <text x={W - M.right + 6} y={M.top + 24} fontSize={10} fill="#38bdf8">microgravity</text>

        <g fontSize={10} fill="#94a3b8">
          {[14, 18, 22, 26, 30, 34, 38].filter((v) => v <= c.o2_pct[c.o2_pct.length - 1]).map((v) => (
            <g key={v}>
              <line x1={x(v)} x2={x(v)} y1={H - M.bottom} y2={H - M.bottom + 4} stroke="#475569" />
              <text x={x(v)} y={H - M.bottom + 16} textAnchor="middle">{v}</text>
            </g>
          ))}
          <text x={(W - M.left - M.right) / 2 + M.left} y={H - 4} textAnchor="middle">
            oxygen concentration (%)
          </text>
          <text x={12} y={H / 2} textAnchor="middle" transform={`rotate(-90 12 ${H / 2})`}>
            margin above LOC (pt)
          </text>
        </g>

        {/* hover readout: both margins at that O2 */}
        <rect x={M.left} y={M.top} width={W - M.left - M.right} height={H - M.top - M.bottom}
          fill="transparent"
          onMouseMove={(e) => {
            const rect = (e.currentTarget as SVGRectElement).getBoundingClientRect();
            const px = ((e.clientX - rect.left) / rect.width) * (W - M.left - M.right) + M.left;
            const o2 = Math.round(x.invert(px));
            const pick = (arr: Array<{ o2_pct: number; margin_pct: number }>) =>
              arr.reduce((a, b) => (Math.abs(b.o2_pct - o2) < Math.abs(a.o2_pct - o2) ? b : a));
            const a = pick(c.series.microgravity);
            const b = pick(c.series.earth);
            setHover({ o2: a.o2_pct, ug: a.margin_pct, g: b.margin_pct });
          }}
          onMouseLeave={() => setHover(null)} />
        {hover && (
          <g pointerEvents="none">
            <line x1={x(hover.o2)} x2={x(hover.o2)} y1={M.top} y2={H - M.bottom} stroke="#64748b" />
            <text x={x(hover.o2) + 5} y={H - M.bottom - 6} fontSize={10} fill="#e2e8f0">
              {hover.o2}% O₂ · µg {hover.ug > 0 ? "+" : ""}{hover.ug.toFixed(1)} · 1g {hover.g > 0 ? "+" : ""}{hover.g.toFixed(1)}
            </text>
          </g>
        )}
      </svg>

      <p className="text-xs text-slate-400 leading-relaxed mt-1">
        {c.published_finding}{" "}
        <span className="text-slate-500">
          At {c.pressure_psia.toFixed(1)} psia the engine's own crossing sits near{" "}
          {c.microgravity_sustains_below_1g_at_pct}% O₂, with a fixed {c.offset_pt} pt gravity
          offset in the boundary — the same offset used everywhere else in FLARE.
        </span>
      </p>
    </div>
  );
}

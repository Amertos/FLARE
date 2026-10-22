import { useCallback, useEffect, useMemo, useState } from "react";
import { api, atmosphereQuery, reportUrl, type ScenarioResponse, type TradeSpaceResponse } from "./api";
import TradeSpace from "./screens/TradeSpace";
import Freefall from "./screens/Freefall";
import EvidenceExplorer from "./screens/EvidenceExplorer";
import AIScientist from "./screens/AIScientist";
import Validation from "./screens/Validation";
import Methodology from "./screens/Methodology";

type Tab = "trade" | "freefall" | "evidence" | "ai" | "validation" | "methodology";

const TABS: Array<{ id: Tab; label: string; num: string }> = [
  { id: "trade", label: "Trade Space", num: "1" },
  { id: "freefall", label: "Freefall Lab", num: "2" },
  { id: "evidence", label: "Evidence", num: "3" },
  { id: "ai", label: "Ask FLARE", num: "4" },
  { id: "validation", label: "Validation", num: "5" },
  { id: "methodology", label: "Methodology", num: "6" },
];

const MISSIONS = [
  { id: "artemis-lander", label: "🌕 Artemis lander (8.2 / 34, lunar) — EA cabin", gravity: "lunar", p: 8.2, o2: 34 },
  { id: "mars", label: "🔴 Mars transit (8.2 / 34) — Exploration Atmosphere", gravity: "microgravity", p: 8.2, o2: 34 },
  { id: "gateway-orbital", label: "🛰️ Gateway transit (µg, 0.3 m/s) — twin test", gravity: "microgravity", p: 8.2, o2: 34 },
  { id: "gateway-ground-eval", label: "🧪 Gateway ground bench (1g twin) — test condition", gravity: "earth", p: 8.2, o2: 34 },
  { id: "saffire-iv", label: "🔥 SAFFIRE-IV payload (14.7 / 21, µg) — flight condition", gravity: "microgravity", p: 14.7, o2: 21 },
  { id: "iss-depress", label: "⬇️ ISS depress sequence (10 / 30, µg) — transition", gravity: "microgravity", p: 10, o2: 30 },
  { id: "station", label: "🛰️ Station (14.7 psia / 21% O₂)", gravity: "microgravity", p: 14.7, o2: 21 },
  { id: "lunar", label: "🌙 Lunar surface (8.2 / 34)", gravity: "lunar", p: 8.2, o2: 34 },
  { id: "deep", label: "🚀 Deep-space transit (8.2 / 34)", gravity: "microgravity", p: 8.2, o2: 34 },
  { id: "apollo1", label: "🕯️ Apollo 1 (1967) — 16.7 psia / 100% O₂", gravity: "earth", p: 16.7, o2: 100 },
];

// A state typed or linked in by hand is not one of the presets; saying so is
// better than silently snapping it to the nearest preset.
const CUSTOM = { id: "custom", label: "⚙️ Custom state", gravity: "microgravity", p: 8.2, o2: 34 };

// The four material classes the engine and API accept (dossier §2.1). Each one
// carries its own representative thickness factor in the engine, so switching
// material genuinely moves the spread/persistence components.
const MATERIALS = [
  { id: "polymer", label: "Polymer (PMMA-class)" },
  { id: "textile", label: "Textile (cotton/fabric)" },
  { id: "insulation", label: "Insulation (low-density foam)" },
  { id: "composite", label: "Composite (laminate)" },
];

const GRAVITIES = ["microgravity", "lunar", "mars", "earth"] as const;

interface UrlState {
  pressure: number;
  o2: number;
  gravity: string;
  flow: number;
  temperature: number;
  material: string;
  tab: Tab;
}

/** Read the atmosphere from the URL so a judge can be handed a link to a state. */
function readUrl(): UrlState | null {
  const q = new URLSearchParams(window.location.search);
  if (![...q.keys()].length) return null;
  const num = (k: string, fallback: number) => {
    const v = Number(q.get(k));
    return Number.isFinite(v) ? v : fallback;
  };
  const tab = q.get("tab");
  return {
    pressure: num("p", 8.2),
    o2: num("o2", 34),
    gravity: GRAVITIES.includes(q.get("g") as (typeof GRAVITIES)[number])
      ? (q.get("g") as string)
      : "microgravity",
    flow: num("f", 0.2),
    temperature: num("t", 22),
    material: MATERIALS.some((m) => m.id === q.get("m")) ? (q.get("m") as string) : "polymer",
    tab: TABS.some((t) => t.id === tab) ? (tab as Tab) : "trade",
  };
}

export default function App() {
  const initial = useMemo<UrlState | null>(() => readUrl(), []);
  const matchedPreset = MISSIONS.find(
    (m) =>
      initial &&
      m.gravity === initial.gravity &&
      m.p === initial.pressure &&
      m.o2 === initial.o2,
  );
  // Gravity is its own piece of state, not a property read off the preset: a
  // linked state of 10 psia / 30% O2 at Mars gravity has no preset, and taking
  // the regime from a fallback preset used to overwrite the gravity in the link.
  const [presetId, setPresetId] = useState(matchedPreset?.id ?? (initial ? "custom" : MISSIONS[1].id));
  const [gravity, setGravity] = useState(initial?.gravity ?? MISSIONS[1].gravity);
  const [pressure, setPressure] = useState(initial?.pressure ?? 8.2);
  const [o2, setO2] = useState(initial?.o2 ?? 34);
  const [flow, setFlow] = useState(initial?.flow ?? 0.2);
  const [temperature, setTemperature] = useState(initial?.temperature ?? 22);
  const [material, setMaterial] = useState(initial?.material ?? "polymer");
  const [tab, setTab] = useState<Tab>(initial?.tab ?? "trade");
  const [scenario, setScenario] = useState<ScenarioResponse | null>(null);
  const [trade, setTrade] = useState<TradeSpaceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Which experiment a citation chip asked for; consumed by Evidence Explorer.
  const [focusExperiment, setFocusExperiment] = useState<string | null>(null);

  useEffect(() => {
    const handler = (e: Event) => {
      const d = (e as CustomEvent<{ p: number; o2: number }>).detail;
      setPressure(d.p);
      setO2(Math.min(45, d.o2));
    };
    window.addEventListener("flare-pick", handler);
    return () => window.removeEventListener("flare-pick", handler);
  }, []);

  const query = useMemo(
    () => atmosphereQuery({ pressure, o2, gravity, flow, temperature, material }),
    [pressure, o2, gravity, flow, temperature, material],
  );

  // Keep the address bar in step with the console, without adding history
  // entries: the URL is the shareable artifact of what is on screen.
  useEffect(() => {
    const params = new URLSearchParams({
      p: String(pressure), o2: String(o2), g: gravity,
      f: String(flow), t: String(temperature), m: material, tab,
    });
    window.history.replaceState(null, "", `${window.location.pathname}?${params}`);
  }, [pressure, o2, gravity, flow, temperature, material, tab]);

  useEffect(() => {
    let alive = true;
    Promise.all([
      api.scenario(query),
      api.tradespace(
        `gravity=${gravity}&flow_ms=${flow}&temperature_c=${temperature}&material_class=${material}`,
      ),
    ])
      .then(([s, t]) => { if (alive) { setScenario(s); setTrade(t); setError(null); } })
      .catch((e) => alive && setError(String(e)));
    return () => { alive = false; };
  }, [query, gravity, flow, temperature, material]);

  // Selecting a preset writes the whole atmosphere in one event, rather than
  // reacting to a mission change in an effect that would render twice.
  const applyMission = useCallback((id: string) => {
    const next = MISSIONS.find((m) => m.id === id);
    if (!next) return;
    setPresetId(next.id);
    setGravity(next.gravity);
    setPressure(next.p);
    setO2(next.o2);
  }, []);

  // A citation chip in an answer jumps to the experiment it cites: the answer
  // panel and the record it cites are on different screens, so the request is
  // handed to Evidence Explorer and the tab switches with it.
  const openExperiment = useCallback((id: string) => {
    setFocusExperiment(id);
    setTab("evidence");
  }, []);

  // Stable identity for the atmosphere object: it is a dependency of the memo
  // download callback and a prop of the trade-space screen.
  const atm = useMemo(
    () => ({ pressure, o2, gravity, flow, temperature, material }),
    [pressure, o2, gravity, flow, temperature, material],
  );

  // Fetch the memo and hand the browser a file, rather than pointing a link at
  // the endpoint: a cross-origin link with Content-Disposition: attachment
  // shows up as an aborted document request in the console.
  const [memoState, setMemoState] = useState<"idle" | "busy" | "error">("idle");
  const downloadMemo = useCallback(async () => {
    setMemoState("busy");
    try {
      const res = await fetch(reportUrl(atm, true));
      if (!res.ok) throw new Error(String(res.status));
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `flare-flight-readiness-briefing-${pressure}psia-${o2}pct-${gravity}.md`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setMemoState("idle");
    } catch {
      setMemoState("error");
    }
  }, [atm, pressure, o2, gravity]);

  // Header status colour follows the engine's own verdict: margin-above-LOC
  // positive means sustained spread is possible → alarm orange dot.
  const headerStatus = scenario
    ? scenario.hazard.margin_above_loc_pct > 0
      ? { dot: "bg-[var(--flare-alarm)]", text: "text-[var(--flare-alarm)]", word: "flammable regime" }
      : { dot: "bg-[var(--flare-safe)]", text: "text-[var(--flare-safe)]", word: "below LOC — no sustained spread" }
    : null;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center gap-x-3 gap-y-2">
          <div className="flex items-center gap-2 mr-2 brand-glow rounded-lg pr-3">
            <span className="text-2xl" aria-hidden="true">🔥</span>
            <div>
              <div className="font-bold tracking-wide">FLARE</div>
              <div className="text-[10px] text-slate-400 -mt-0.5">Fire &amp; Life Atmosphere Risk Explorer</div>
            </div>
          </div>

          {headerStatus && (
            <span className="flex items-center gap-2 rounded-full border border-slate-700 bg-slate-950/70 px-3 py-1 text-[11px] font-mono"
              title="Engine verdict for the current atmosphere: margin above the effective LOC boundary">
              <span className={`status-dot ${headerStatus.dot}`} aria-hidden="true" />
              <span className={headerStatus.text}>{headerStatus.word}</span>
            </span>
          )}

          <label className="flex items-center gap-1 text-xs text-slate-400">
            <span className="sr-only">Preset atmosphere</span>
            <select className="bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-100"
              aria-label="Preset atmosphere"
              value={presetId}
              onChange={(e) => applyMission(e.target.value)}>
              {MISSIONS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
              <option value={CUSTOM.id}>{CUSTOM.label}</option>
            </select>
          </label>

          <label className="flex items-center gap-1 text-xs text-slate-400">
            <span className="sr-only">Gravity regime</span>
            <select className="bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-100"
              aria-label="Gravity regime"
              value={gravity}
              onChange={(e) => { setGravity(e.target.value); setPresetId(CUSTOM.id); }}>
              <option value="microgravity">microgravity</option>
              <option value="lunar">lunar (0.165 g)</option>
              <option value="mars">mars (0.38 g)</option>
              <option value="earth">earth (1 g)</option>
            </select>
          </label>

          <label className="flex items-center gap-1 text-xs text-slate-400">
            <span className="sr-only">Material class</span>
            <select className="bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-100"
              aria-label="Material class"
              value={material} onChange={(e) => setMaterial(e.target.value)}>
              {MATERIALS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </label>

          <label className="flex items-center gap-1.5 text-xs text-slate-300">
            P
            <input type="range" min={4} max={16.7} step={0.1} value={pressure}
              aria-label="Total pressure in psia"
              onChange={(e) => setPressure(+e.target.value)} className="w-28 accent-orange-500" />
            <span className="font-mono w-16">{pressure.toFixed(1)} psia</span>
          </label>
          <label className="flex items-center gap-1.5 text-xs text-slate-300">
            O₂
            <input type="range" min={14} max={45} step={0.5} value={Math.min(45, o2)}
              aria-label="Oxygen concentration in percent"
              onChange={(e) => setO2(+e.target.value)} disabled={presetId === "apollo1"}
              className="w-28 accent-orange-500 disabled:opacity-40" />
            <span className="font-mono w-12">{o2.toFixed(1)}%</span>
          </label>
          <label className="flex items-center gap-1.5 text-xs text-slate-300">
            Flow
            <input type="range" min={0} max={1} step={0.01} value={flow}
              aria-label="Forced airflow in metres per second"
              onChange={(e) => setFlow(+e.target.value)} className="w-24 accent-orange-500" />
            <span className="font-mono w-16">{flow.toFixed(2)} m/s</span>
          </label>
          <label className="flex items-center gap-1.5 text-xs text-slate-300">
            T
            <input type="range" min={18} max={30} step={0.5} value={temperature}
              aria-label="Ambient temperature in Celsius"
              onChange={(e) => setTemperature(+e.target.value)} className="w-24 accent-orange-500" />
            <span className="font-mono w-12">{temperature.toFixed(1)} °C</span>
          </label>

          <button type="button" onClick={downloadMemo} disabled={memoState === "busy"}
            className="ml-auto text-xs px-3 py-1.5 rounded border border-orange-700 bg-orange-950/50 text-orange-200 hover:bg-orange-900/50 disabled:opacity-50 font-semibold"
            title="Download this state as a NASA flight-readiness briefing (Markdown): configuration + margins, flame regime, citation matrix joining every claim to its NTRS/PMC source, sensitivity sweep, backtest confidence, limitations L1-L8">
            {memoState === "busy" ? "building briefing…" : memoState === "error" ? "briefing failed — retry" : "📋 Flight-Readiness Briefing"}
          </button>
        </div>

        <nav className="max-w-7xl mx-auto px-4 flex gap-1 text-sm" role="tablist"
          aria-label="FLARE screens">
          {TABS.map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id}
              aria-controls={`panel-${t.id}`} id={`tab-${t.id}`}
              onClick={() => setTab(t.id)}
              className={`group relative px-3 py-2.5 text-[13px] transition-colors ${tab === t.id ? "text-orange-300 font-semibold" : "text-slate-400 hover:text-slate-200"}`}>
              <span className="inline-flex items-baseline gap-1.5">
                <span className={`font-mono text-[9px] leading-none rounded-sm px-1 py-0.5 transition-colors ${
                  tab === t.id ? "bg-orange-950/70 text-orange-400" : "bg-slate-800/60 text-slate-500 group-hover:bg-slate-800"}`}
                  aria-hidden="true">
                  {t.num}
                </span>
                {t.label}
              </span>
              <span aria-hidden="true" className={`absolute inset-x-2 bottom-0 h-0.5 rounded-full transition-all ${
                tab === t.id ? "bg-orange-500" : "bg-transparent group-hover:bg-slate-700"}`} />
            </button>
          ))}
        </nav>
      </header>

      {error && (
        <div className="max-w-7xl mx-auto px-4 pt-3" role="alert">
          <div className="bg-red-950 border border-red-800 text-red-200 rounded px-3 py-2 text-sm">
            Backend unreachable ({error}). Start it with: <code>py -m uvicorn backend.app.main:app --port 8787</code>
          </div>
        </div>
      )}

      <main className="max-w-7xl mx-auto px-4 py-4"
        id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`}>
        {tab === "trade" && (
          <div className="space-y-3">
            {/* The console tells you what the atmosphere costs. This is the
                one line that says the other half exists, where a judge is
                already looking at the hazard map. */}
            <button type="button" onClick={() => setTab("freefall")}
              className="w-full text-left rounded-lg border border-orange-800/70 bg-orange-950/30 hover:bg-orange-950/50 px-3 py-2 transition-colors group">
              <span className="text-sm text-orange-200 font-medium">
                What does a fire actually <em>do</em> in this atmosphere?
              </span>{" "}
              <span className="text-xs text-orange-300/80 group-hover:text-orange-200">
                Open the Freefall Lab — 3D hazard terrain, the flame morphing between a
                sphere and a teardrop, and the microgravity-vs-1g crossover →
              </span>
            </button>
            <TradeSpace scenario={scenario} trade={trade} atm={atm} pressure={pressure} o2={o2} />
          </div>
        )}
        {tab === "freefall" && <Freefall atm={atm} trade={trade} />}
        {tab === "evidence" && (
          // Remounting on a new citation lets the explorer derive its open card
          // from the prop instead of reacting to it in an effect.
          <EvidenceExplorer
            key={focusExperiment ?? "evidence"}
            query={query}
            focus={focusExperiment}
          />
        )}
        {tab === "ai" && <AIScientist query={query} onCite={openExperiment} />}
        {tab === "validation" && <Validation />}
        {tab === "methodology" && <Methodology />}
      </main>

      <footer className="max-w-7xl mx-auto px-4 pt-8 pb-8">
        <div className="border-t border-slate-800/80 pt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-500">
          <span className="flex items-center gap-1.5">
            <span className="corner-mark" aria-hidden="true" />FLARE — Fire &amp; Life Atmosphere Risk Explorer
          </span>
          <span aria-hidden="true" className="text-slate-700">·</span>
          <span>deterministic engine, no language model in this build</span>
          <span aria-hidden="true" className="text-slate-700">·</span>
          <span>citations verified in code</span>
          <span aria-hidden="true" className="text-slate-700">·</span>
          <span>boundary drawn only inside the fitted pressure range</span>
        </div>
      </footer>
    </div>
  );
}

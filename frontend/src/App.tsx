import { useCallback, useEffect, useMemo, useState } from "react";
import { api, atmosphereQuery, reportUrl, type ScenarioResponse, type TradeSpaceResponse } from "./api";
import TradeSpace from "./screens/TradeSpace";
import Freefall from "./screens/Freefall";
import EvidenceExplorer from "./screens/EvidenceExplorer";
import AIScientist from "./screens/AIScientist";
import Validation from "./screens/Validation";
import Methodology from "./screens/Methodology";
import Countermoves from "./screens/Countermoves";
import DesignSearch from "./screens/DesignSearch";

// Debounce a single scalar so dragging a slider does not fire one API call
// per pixel. Objects must NOT be passed here: a fresh object literal every
// render would re-arm the timer forever and re-render (and re-fetch) on a loop.
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debouncedValue;
}

type Tab = "trade" | "levers" | "design" | "freefall" | "evidence" | "ai" | "validation" | "methodology";

const TABS: Array<{ id: Tab; label: string; num: string }> = [
  { id: "trade", label: "Trade Space", num: "1" },
  { id: "levers", label: "Countermoves", num: "2" },
  { id: "design", label: "Design Search", num: "3" },
  { id: "freefall", label: "Freefall Lab", num: "4" },
  { id: "evidence", label: "Evidence", num: "5" },
  { id: "ai", label: "Ask FLARE", num: "6" },
  { id: "validation", label: "Validation", num: "7" },
  { id: "methodology", label: "Methodology", num: "8" },
];

const MISSIONS = [
  { id: "artemis-lander", label: "🌕 Artemis lander", gravity: "lunar", p: 8.2, o2: 34 },
  { id: "mars", label: "🔴 Mars transit", gravity: "microgravity", p: 8.2, o2: 34 },
  { id: "gateway-orbital", label: "🛰️ Gateway transit", gravity: "microgravity", p: 8.2, o2: 34 },
  { id: "gateway-ground-eval", label: "🧪 Gateway ground bench", gravity: "earth", p: 8.2, o2: 34 },
  { id: "saffire-iv", label: "🔥 SAFFIRE-IV", gravity: "microgravity", p: 14.7, o2: 21 },
  { id: "iss-depress", label: "⬇️ ISS depress", gravity: "microgravity", p: 10, o2: 30 },
  { id: "station", label: "🛰️ Station", gravity: "microgravity", p: 14.7, o2: 21 },
  { id: "lunar", label: "🌙 Lunar surface", gravity: "lunar", p: 8.2, o2: 34 },
  { id: "deep", label: "🚀 Deep-space", gravity: "microgravity", p: 8.2, o2: 34 },
  { id: "apollo1", label: "🕯️ Apollo 1", gravity: "earth", p: 16.7, o2: 100 },
];

const CUSTOM = { id: "custom", label: "⚙️ Custom state", gravity: "microgravity", p: 8.2, o2: 34 };

const MATERIALS = [
  { id: "polymer", label: "Polymer (PMMA)" },
  { id: "textile", label: "Textile (Cotton)" },
  { id: "insulation", label: "Insulation" },
  { id: "composite", label: "Composite" },
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

function readUrl(): UrlState | null {
  const q = new URLSearchParams(window.location.search);
  if (![...q.keys()].length) return null;
  const num = (k: string, fallback: number) => {
    const raw = q.get(k);
    if (raw === null || raw.trim() === "") return fallback;
    const v = Number(raw);
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
  
  const [presetId, setPresetId] = useState(initial ? "custom" : MISSIONS[1].id);
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
  const [focusExperiment, setFocusExperiment] = useState<string | null>(null);

  // Debounce each scalar, then rebuild the atmosphere object from the
  // debounced values. The memo keeps that object referentially stable, so the
  // fetch effect below only re-runs when a debounced value actually changes.
  const debouncedPressure = useDebounce(pressure, 250);
  const debouncedO2 = useDebounce(o2, 250);
  const debouncedGravity = useDebounce(gravity, 250);
  const debouncedFlow = useDebounce(flow, 250);
  const debouncedTemperature = useDebounce(temperature, 250);
  const debouncedMaterial = useDebounce(material, 250);

  const debouncedAtm = useMemo(
    () => ({
      pressure: debouncedPressure,
      o2: debouncedO2,
      gravity: debouncedGravity,
      flow: debouncedFlow,
      temperature: debouncedTemperature,
      material: debouncedMaterial,
    }),
    [debouncedPressure, debouncedO2, debouncedGravity, debouncedFlow,
      debouncedTemperature, debouncedMaterial],
  );

  useEffect(() => {
    const handler = (e: Event) => {
      const d = (e as CustomEvent<{ p: number; o2: number }>).detail;
      setPressure(d.p);
      setO2(Math.min(45, d.o2));
      setPresetId(CUSTOM.id);
    };
    window.addEventListener("flare-pick", handler);
    return () => window.removeEventListener("flare-pick", handler);
  }, []);

  const query = useMemo(
    () => atmosphereQuery(debouncedAtm),
    [debouncedAtm],
  );

  // The trade-space grid depends only on gravity/flow/temperature/material.
  const tradeQuery = useMemo(
    () => `gravity=${debouncedAtm.gravity}&flow_ms=${debouncedAtm.flow}`
      + `&temperature_c=${debouncedAtm.temperature}&material_class=${debouncedAtm.material}`,
    [debouncedAtm],
  );

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
      api.tradespace(tradeQuery),
    ])
      .then(([s, t]) => {
        if (!alive) return;
        setScenario(s);
        setTrade(t);
        setError(null);
      })
      .catch((e) => alive && setError(String(e)));
    return () => { alive = false; };
  }, [query, tradeQuery]);

  const applyMission = useCallback((id: string) => {
    const next = MISSIONS.find((m) => m.id === id);
    if (!next) return;
    setPresetId(next.id);
    setGravity(next.gravity);
    setPressure(next.p);
    setO2(next.o2);
  }, []);

  const openExperiment = useCallback((id: string) => {
    setFocusExperiment(id);
    setTab("evidence");
  }, []);

  const currentAtm = useMemo(
    () => ({ pressure, o2, gravity, flow, temperature, material }),
    [pressure, o2, gravity, flow, temperature, material],
  );

  const [memoState, setMemoState] = useState<"idle" | "busy" | "error">("idle");
  const downloadMemo = useCallback(async () => {
    setMemoState("busy");
    try {
      const res = await fetch(reportUrl(currentAtm, true));
      if (!res.ok) throw new Error(String(res.status));
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `flare-briefing-${currentAtm.pressure}psia-${currentAtm.o2}o2.md`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setMemoState("idle");
    } catch {
      setMemoState("error");
    }
  }, [currentAtm]);

  const headerStatus = scenario
    ? scenario.hazard.margin_above_loc_pct > 0
      ? { dot: "bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.6)]", text: "text-orange-400", word: "Flammable Regime" }
      : { dot: "bg-emerald-500", text: "text-emerald-400", word: "Below LOC (Safe)" }
    : null;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-orange-500/30">
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-30">
        <div className="max-w-[1600px] mx-auto px-4 py-3 flex flex-wrap items-center gap-6">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <span className="text-2xl filter drop-shadow-sm" aria-hidden="true">🔥</span>
            <div>
              <div className="font-black tracking-tighter text-lg leading-none">FLARE</div>
              <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-1">Atmosphere Risk Explorer</div>
            </div>
          </div>

          {/* Status Badge */}
          {headerStatus && (
            <div className="flex items-center gap-2 rounded-full border border-slate-700/50 bg-slate-950/50 px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider">
              <span className={`h-2 w-2 rounded-full ${headerStatus.dot}`} aria-hidden="true" />
              <span className={headerStatus.text}>{headerStatus.word}</span>
            </div>
          )}

          {/* Main Controls Group */}
          <div className="flex items-center gap-4 bg-slate-800/40 p-1 rounded-lg border border-slate-700/30">
            <select className="bg-transparent text-sm font-medium px-2 py-1 outline-none"
              value={presetId} onChange={(e) => applyMission(e.target.value)}>
              {MISSIONS.map((m) => <option key={m.id} value={m.id} className="bg-slate-900">{m.label}</option>)}
              <option value={CUSTOM.id} className="bg-slate-900">{CUSTOM.label}</option>
            </select>
            <div className="w-px h-4 bg-slate-700" />
            <select className="bg-transparent text-sm font-medium px-2 py-1 outline-none"
              value={gravity} onChange={(e) => { setGravity(e.target.value); setPresetId(CUSTOM.id); }}>
              <option value="microgravity" className="bg-slate-900">µg (Microgravity)</option>
              <option value="lunar" className="bg-slate-900">0.16g (Lunar)</option>
              <option value="mars" className="bg-slate-900">0.38g (Mars)</option>
              <option value="earth" className="bg-slate-900">1.0g (Earth)</option>
            </select>
            <div className="w-px h-4 bg-slate-700" />
            <select className="bg-transparent text-sm font-medium px-2 py-1 outline-none"
              value={material}
              aria-label="Material class"
              onChange={(e) => { setMaterial(e.target.value); setPresetId(CUSTOM.id); }}>
              {MATERIALS.map((m) => <option key={m.id} value={m.id} className="bg-slate-900">{m.label}</option>)}
            </select>
          </div>

          {/* Parameters Sliders */}
          <div className="flex items-center gap-6 flex-grow min-w-fit">
            <div className="flex flex-col gap-1 flex-1 max-w-[120px]">
              <div className="flex justify-between text-[10px] font-bold text-slate-500 uppercase tracking-tighter">
                <span>Pressure</span>
                <span className="text-slate-300 font-mono">{pressure.toFixed(1)}</span>
              </div>
              <input type="range" min={4} max={16.7} step={0.1} value={pressure}
                onChange={(e) => { setPressure(+e.target.value); setPresetId(CUSTOM.id); }}
                className="accent-orange-500 h-1.5" />
            </div>

            <div className="flex flex-col gap-1 flex-1 max-w-[120px]">
              <div className="flex justify-between text-[10px] font-bold text-slate-500 uppercase tracking-tighter">
                <span>Oxygen %</span>
                <span className="text-slate-300 font-mono">{o2.toFixed(1)}</span>
              </div>
              <input type="range" min={14} max={45} step={0.5} value={o2}
                disabled={presetId === "apollo1"}
                onChange={(e) => { setO2(+e.target.value); setPresetId(CUSTOM.id); }}
                className="accent-orange-500 h-1.5 disabled:opacity-20" />
            </div>

            <div className="flex flex-col gap-1 flex-1 max-w-[100px]">
              <div className="flex justify-between text-[10px] font-bold text-slate-500 uppercase tracking-tighter">
                <span>Flow</span>
                <span className="text-slate-300 font-mono">{flow.toFixed(2)}</span>
              </div>
              <input type="range" min={0} max={1} step={0.01} value={flow}
                onChange={(e) => { setFlow(+e.target.value); setPresetId(CUSTOM.id); }}
                className="accent-orange-500 h-1.5" />
            </div>

            <div className="flex flex-col gap-1 flex-1 max-w-[100px]">
              <div className="flex justify-between text-[10px] font-bold text-slate-500 uppercase tracking-tighter">
                <span>Temp °C</span>
                <span className="text-slate-300 font-mono">{temperature.toFixed(0)}</span>
              </div>
              <input type="range" min={-20} max={60} step={1} value={temperature}
                onChange={(e) => { setTemperature(+e.target.value); setPresetId(CUSTOM.id); }}
                className="accent-orange-500 h-1.5" />
            </div>
          </div>

          <button type="button" onClick={downloadMemo} disabled={memoState === "busy"}
            className="text-[11px] font-bold uppercase tracking-widest px-4 py-2 rounded bg-orange-600 hover:bg-orange-500 transition-colors disabled:opacity-50">
            {memoState === "busy" ? "Generating..." : "Download Report"}
          </button>
        </div>

        {/* Tab Navigation */}
        <nav className="max-w-[1600px] mx-auto px-4 flex gap-1 overflow-x-auto no-scrollbar">
          {TABS.map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`px-4 py-3 text-[12px] font-bold uppercase tracking-wider transition-all border-b-2 ${
                tab === t.id ? "border-orange-500 text-orange-400" : "border-transparent text-slate-500 hover:text-slate-300 hover:border-slate-700"
              }`}>
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      {error && (
        <div className="max-w-7xl mx-auto px-4 mt-4 animate-in fade-in slide-in-from-top-2">
          <div className="bg-red-500/10 border border-red-500/50 text-red-400 px-4 py-3 rounded text-sm font-medium">
             ⚠️ Engine Connection Error: {error}
          </div>
        </div>
      )}

      <main className="max-w-[1600px] mx-auto px-4 py-6 min-h-[calc(100vh-180px)]">
        {tab === "trade" && (
          <div className="space-y-6">
            <TradeSpace scenario={scenario} trade={trade} atm={currentAtm} pressure={pressure} o2={o2} />
          </div>
        )}
        {tab === "freefall" && <Freefall atm={currentAtm} trade={trade} />}
        {tab === "levers" && <Countermoves query={query} />}
        {tab === "design" && <DesignSearch query={query} />}
        {tab === "evidence" && (
          <EvidenceExplorer key={focusExperiment ?? "evidence"} query={query} focus={focusExperiment} />
        )}
        {tab === "ai" && <AIScientist query={query} onCite={openExperiment} />}
        {tab === "validation" && <Validation />}
        {tab === "methodology" && <Methodology />}
      </main>

      <footer className="border-t border-slate-800/50 mt-12 py-8 bg-slate-900/30">
        <div className="max-w-7xl mx-auto px-4 flex flex-col md:flex-row justify-between items-center gap-4 text-[10px] font-bold text-slate-500 uppercase tracking-widest">
          <div className="flex items-center gap-2">
             <div className="h-1.5 w-1.5 bg-orange-500 rounded-full" />
             FLARE Engine v2.4.0 — Deterministic, No Language Model
          </div>
          <div>Citations Verified against NTRS/PMC Databases</div>
          <div className="text-slate-600">© 2026 FLARE · NASA Space Apps Challenge</div>
        </div>
      </footer>
    </div>
  );
}
import { useEffect, useMemo, useState } from "react";
import { api, type ScenarioResponse, type TradeSpaceResponse } from "./api";
import TradeSpace from "./screens/TradeSpace";
import EvidenceExplorer from "./screens/EvidenceExplorer";
import AIScientist from "./screens/AIScientist";
import Validation from "./screens/Validation";

const MISSIONS = [
  { id: "station", label: "🛰️ Station", gravity: "microgravity", p: 14.7, o2: 21 },
  { id: "mars", label: "🔴 Mars transit", gravity: "microgravity", p: 8.2, o2: 34 },
  { id: "lunar", label: "🌙 Lunar surface", gravity: "lunar", p: 8.2, o2: 34 },
  { id: "deep", label: "🚀 Deep-space transit", gravity: "microgravity", p: 8.2, o2: 34 },
  { id: "apollo1", label: "🕯️ Apollo 1 (1967)", gravity: "earth", p: 16.7, o2: 100 },
];

const MATERIALS = [
  { id: "polymer", label: "Polymer (PMMA-class)" },
  { id: "textile", label: "Textile (cotton/fabric)" },
];

export default function App() {
  const [mission, setMission] = useState(MISSIONS[1]);
  const [pressure, setPressure] = useState(8.2);
  const [o2, setO2] = useState(34);
  const [flow, setFlow] = useState(0.2);
  const [material, setMaterial] = useState("polymer");
  const [tab, setTab] = useState<"trade" | "evidence" | "ai" | "validation">("trade");
  const [scenario, setScenario] = useState<ScenarioResponse | null>(null);
  const [trade, setTrade] = useState<TradeSpaceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [, setPick] = useState<{ p: number; o2: number } | null>(null);

  useEffect(() => {
    const handler = (e: Event) => {
      const d = (e as CustomEvent<{ p: number; o2: number }>).detail;
      setPick(d); setPressure(d.p); setO2(Math.min(45, d.o2));
    };
    window.addEventListener("flare-pick", handler);
    return () => window.removeEventListener("flare-pick", handler);
  }, []);

  const query = useMemo(
    () => `pressure_psia=${pressure}&o2_pct=${o2}&gravity=${mission.gravity}&flow_ms=${flow}&material_class=${material}`,
    [pressure, o2, mission.gravity, flow, material]
  );

  useEffect(() => {
    let alive = true;
    Promise.all([api.scenario(query), api.tradespace(`gravity=${mission.gravity}&flow_ms=${flow}&material_class=${material}`)])
      .then(([s, t]) => { if (alive) { setScenario(s); setTrade(t); setError(null); } })
      .catch((e) => alive && setError(String(e)));
    return () => { alive = false; };
  }, [query, mission.gravity, flow, material]);

  useEffect(() => { setPressure(mission.p); setO2(mission.o2); }, [mission]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 mr-2">
            <span className="text-2xl">🔥</span>
            <div>
              <div className="font-bold tracking-wide">FLARE</div>
              <div className="text-[10px] text-slate-400 -mt-0.5">Fire &amp; Life Atmosphere Risk Explorer</div>
            </div>
          </div>
          <select className="bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm"
            value={mission.id}
            onChange={(e) => setMission(MISSIONS.find((m) => m.id === e.target.value)!)}>
            {MISSIONS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
          <select className="bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-sm"
            value={material} onChange={(e) => setMaterial(e.target.value)}>
            {MATERIALS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
          <label className="flex items-center gap-1.5 text-xs text-slate-300">
            P <input type="range" min={4.5} max={16.7} step={0.1} value={pressure}
              onChange={(e) => setPressure(+e.target.value)} className="w-28 accent-orange-500" />
            <span className="font-mono w-14">{pressure.toFixed(1)} psi</span>
          </label>
          <label className="flex items-center gap-1.5 text-xs text-slate-300">
            O₂ <input type="range" min={14} max={45} step={0.5} value={Math.min(45, o2)}
              onChange={(e) => setO2(+e.target.value)} disabled={mission.id === "apollo1"} className="w-28 accent-orange-500" />
            <span className="font-mono w-12">{o2.toFixed(1)}%</span>
          </label>
          <label className="flex items-center gap-1.5 text-xs text-slate-300">
            Flow <input type="range" min={0} max={0.5} step={0.01} value={flow}
              onChange={(e) => setFlow(+e.target.value)} className="w-24 accent-orange-500" />
            <span className="font-mono w-16">{flow.toFixed(2)} m/s</span>
          </label>
        </div>
        <nav className="max-w-7xl mx-auto px-4 flex gap-1 text-sm">
          {(["trade", "evidence", "ai", "validation"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-3 py-2 border-b-2 transition-colors ${tab === t ? "border-orange-500 text-orange-300 font-semibold" : "border-transparent text-slate-400 hover:text-slate-200"}`}>
              {t === "trade" && "Trade Space"}
              {t === "evidence" && "Evidence Explorer"}
              {t === "ai" && "AI Scientist"}
              {t === "validation" && "Validation"}
            </button>
          ))}
        </nav>
      </header>

      {error && (
        <div className="max-w-7xl mx-auto px-4 pt-3">
          <div className="bg-red-950 border border-red-800 text-red-200 rounded px-3 py-2 text-sm">
            Backend unreachable ({error}). Start it with: <code>py -m uvicorn backend.app.main:app --port 8787</code>
          </div>
        </div>
      )}

      <main className="max-w-7xl mx-auto px-4 py-4">
        {tab === "trade" && <TradeSpace scenario={scenario} trade={trade} mission={mission} pressure={pressure} o2={o2} />}        {tab === "evidence" && <EvidenceExplorer query={query} />}
        {tab === "ai" && <AIScientist query={query} />}
        {tab === "validation" && <Validation />}
      </main>
    </div>
  );
}

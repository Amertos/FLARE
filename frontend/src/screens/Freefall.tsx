import { Suspense, lazy, useEffect, useState } from "react";
import {
  api,
  atmosphereQuery,
  type AtmosphereParams,
  type FlameResponse,
  type MissionScenario,
  type TradeSpaceResponse,
} from "../api";
import CrossoverChart from "../viz/CrossoverChart";
import ComparePanel from "../viz/ComparePanel";
import { ScreenHeader } from "../ui/FlarePanel";

// three.js is the single largest dependency in the bundle; the two WebGL views
// load as their own chunk so the console's other screens stay fast to open.
const HazardTerrain = lazy(() => import("../viz/HazardTerrain"));
const FlameChamber = lazy(() => import("../viz/FlameChamber"));

// Read once at import time, before the console rewrites the address bar with
// its own query string. `?no3d=1` is the escape hatch for a projector or a
// machine without WebGL: the numbers stay, the geometry goes.
const NO_3D = new URLSearchParams(window.location.search).get("no3d") === "1";

function Skeleton({ h, label }: { h: number; label: string }) {
  return (
    <div className="rounded-lg bg-slate-900/60 border border-slate-800 grid place-items-center text-xs text-slate-500"
      style={{ height: h }}>
      loading {label}…
    </div>
  );
}

function Fact({ k, v, tone = "" }: { k: string; v: string; tone?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-slate-800/70 py-1.5">
      <dt className="text-[11px] uppercase tracking-wide text-slate-500">{k}</dt>
      <dd className={`font-mono text-sm text-right ${tone || "text-slate-200"}`}>{v}</dd>
    </div>
  );
}

export default function Freefall({
  atm,
  trade,
}: {
  atm: AtmosphereParams;
  trade: TradeSpaceResponse | null;
}) {
  const [flame, setFlame] = useState<FlameResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [missions, setMissions] = useState<MissionScenario[] | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .flame(atmosphereQuery(atm))
      .then((f) => {
        if (alive) {
          setFlame(f);
          setError(null);
        }
      })
      .catch((e) => alive && setError(String(e)));
    return () => {
      alive = false;
    };
  }, [atm]);

  useEffect(() => {
    let alive = true;
    api.missions().then((m) => { if (alive) setMissions(m.scenarios); }).catch(() => {});
    return () => { alive = false; };
  }, []);

  // Jump-to-scenario: selecting a mission from inside the Freefall Lab writes
  // the whole atmosphere into the console's URL state, exactly like the header
  // preset picker — one mechanism, one truth.
  const applyScenario = (s: MissionScenario) => {
    const q = new URLSearchParams(window.location.search);
    q.set("p", String(s.pressure_psia));
    q.set("o2", String(s.o2_pct));
    q.set("g", s.gravity);
    q.set("f", String(s.flow_ms));
    window.location.search = q.toString();
  };

  // A mission preset matching the current state supplies its context card.
  const matchedMission = missions?.find(
    (s) => s.pressure_psia === atm.pressure && s.o2_pct === atm.o2
      && s.gravity === atm.gravity && s.flow_ms === atm.flow,
  );

  if (error) {
    return (
      <div className="bg-red-950 border border-red-800 text-red-200 rounded px-3 py-2 text-sm" role="alert">
        /api/flame failed ({error}).
      </div>
    );
  }
  if (!flame) return <Skeleton h={320} label="flame regime" />;

  const h = flame.hazard;
  const below = flame.fate.code === "self_extinguishing";
  const tone = below ? "text-emerald-300" : flame.fate.code === "marginal" ? "text-amber-300" : "text-red-300";

  return (
    <div className="space-y-4 screen-enter">
      <ScreenHeader
        eyebrow="Screen 4 · The physics"
        title="Freefall Lab — what fire looks like where there is no “up”"
        lede="The console answers how risky an atmosphere is. This screen answers the question crews ask first: what will the fire do? Every shape, colour and outcome below is either an engine output or a cited published result — the citation list is at the bottom, and it is the whole list."
        aside={
          <span className="flex items-center gap-2">
            <span className="text-[10px] px-2 py-0.5 rounded border border-amber-700 bg-amber-950/40 text-amber-200">
              schematic of published regimes · not a CFD solution (L8)
            </span>
            <span className="flex items-center gap-2 text-xs text-slate-400">
              jump to scenario:
              <select
                aria-label="Jump to a mission flight scenario"
                className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-slate-100"
                value=""
                onChange={(e) => {
                  const s = missions?.find((x) => x.id === e.target.value);
                  if (s) applyScenario(s);
                }}>
                <option value="">choose…</option>
                {missions?.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </span>
          </span>
        }
      />
      {matchedMission && (
        <div className="rounded-lg border border-sky-900/60 bg-sky-950/20 px-3 py-2 text-xs text-slate-300 max-w-4xl">
          <span className="font-semibold text-sky-300">{matchedMission.name}</span>
          <span className="text-slate-500"> · </span>
          {matchedMission.context}{" "}
          <span className="block text-[10px] text-slate-500 font-mono mt-0.5">source: {matchedMission.provenance}</span>
        </div>
      )}

      <div className="grid lg:grid-cols-[1.35fr_1fr] gap-4">
        <section className="space-y-2">
          <div className="flex items-baseline justify-between">
            <h2 className="text-sm font-semibold text-slate-200">Hazard terrain</h2>
            <span className="text-[11px] text-slate-500">
              drag to orbit · scroll to zoom · hover for ignition readout
            </span>
          </div>
          {NO_3D ? (
            <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4 text-sm text-slate-400"
              style={{ height: 420 }}>
              <div className="font-semibold text-slate-300 mb-1">3D disabled (?no3d=1)</div>
              3D is off in this view. The same ignition field is drawn as the flat map on the
              <strong className="text-slate-200"> Trade Space</strong> screen, and the boundary
              numbers are in the panel to the right — no claim on this screen depends on the
              geometry being rendered.
            </div>
          ) : trade ? (
            <Suspense fallback={<Skeleton h={420} label="terrain" />}>
              <HazardTerrain trade={trade} pressure={atm.pressure} o2={atm.o2} />
            </Suspense>
          ) : (
            <Skeleton h={420} label="terrain" />
          )}
          {trade && !NO_3D && (
            <p className="text-[11px] text-slate-500 leading-relaxed">
              👻 <strong className="text-slate-300">1g ghost</strong> overlays the same ignition
              field computed at 1g (engine output, same modifiers), drawn{' '}
              <em>2 ignition points below</em> the µg surface so the two sheets do not
              interpenetrate; the gap between them is the µg-vs-1g boundary separation the
              crossover chart plots.
            </p>
          )}
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-200">The fire in freefall</h2>
          {NO_3D ? (
            <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
              <div className="text-2xl mb-1" aria-hidden="true">
                {flame.regime.buoyant_convection ? "🔥" : "🔵"}
              </div>
              <div className="font-semibold">{flame.regime.label}</div>
              <p className="text-xs text-slate-400 mt-1">{flame.regime.note}</p>
              <p className="text-xs mt-2">
                <span className="text-slate-500">outcome: </span>
                <span className={tone}>{flame.fate.label}</span>
              </p>
            </div>
          ) : (
            <Suspense fallback={<Skeleton h={300} label="chamber" />}>
              <FlameChamber flame={flame} atmosphere={atm} />
            </Suspense>
          )}

          <dl className="rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-1.5">
            <Fact k="regime" v={flame.regime.shape === "spherical" ? "spherical (µg)" : "teardrop (buoyant)"} />
            <Fact k="colour" v={flame.regime.colour_tendency} />
            <Fact k="airflow band" v={flame.flow_regime?.band ?? "n/a"} />
            <Fact
              k="cool-flame phase"
              v={flame.cool_flame_phase?.possible ? "possible (qualitative)" : "not indicated"}
              tone={flame.cool_flame_phase?.possible ? "text-cyan-300" : ""}
            />
            <Fact k="front rate" v={`${flame.front_speed_relative.toFixed(0)}% of Saffire-I`} />
            <Fact k="effective LOC" v={`${h.effective_loc_pct.toFixed(2)}% O₂`} />
            <Fact
              k="margin above LOC"
              v={`${h.margin_above_loc_pct > 0 ? "+" : ""}${h.margin_above_loc_pct.toFixed(2)} pt`}
              tone={h.margin_above_loc_pct <= 0 ? "text-emerald-300" : "text-red-300"}
            />
            <Fact k="spread index" v={h.spread.toFixed(1)} />
            <Fact k="ignition index" v={h.ignition.toFixed(1)} />
          </dl>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            {flame.reference.note}
          </p>
        </section>
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-slate-200">
          “Space burns slower” is not a rule
        </h2>
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
          <CrossoverChart flame={flame} />
        </div>
      </section>

      <ComparePanel atm={atm} flame={flame} />

      <section className="space-y-2">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold text-slate-200">Sources for every visual claim</h2>
          <span className="text-[11px] text-slate-500">
            {flame.citations.length} entries · returned by the API with the figure, not added in the UI
          </span>
        </div>
        <ol className="space-y-2">
          {flame.citations.map((c) => (
            <li key={c.id} className="rounded border border-slate-800 bg-slate-900/40 px-3 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                  {c.id}
                </span>
                <span className="text-[10px] uppercase tracking-wide text-slate-500">{c.kind}</span>
              </div>
              <p className="text-xs text-slate-300 mt-1 leading-relaxed">{c.claim}</p>
              <a href={c.url} target="_blank" rel="noreferrer noopener"
                className="text-[11px] text-orange-300 hover:text-orange-200 underline decoration-dotted">
                {c.source}
              </a>
            </li>
          ))}
        </ol>
      </section>

      <section className="rounded border border-slate-800 bg-slate-900/30 p-3">
        <h3 className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">
          What this screen does not claim
        </h3>
        <ul className="text-xs text-slate-400 space-y-1 list-disc list-inside leading-relaxed">
          {flame.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
          <li>
            Hover readouts, ember particles and the 1g ghost surface are renderings of engine
            values; none of them change a number, and the ghost surface is the same field at 1g,
            not a 1g experiment record.
          </li>
        </ul>
      </section>
    </div>
  );
}

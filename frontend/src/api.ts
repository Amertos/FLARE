// Typed FLARE API client.
// The deployed product serves the API same-origin through
// api/index.py (vercel.json), so the production build talks to "" and needs
// no CORS; local development still points at the uvicorn server on :8787.
const BASE = import.meta.env.DEV ? "http://localhost:8787" : "";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

export interface HazardVector {
  ignition: number; spread: number; persistence: number;
  heat_release: number; extinction_margin: number;
  crew: { po2_psia: number; normoxia_pct: number; crew_safe: boolean };
  effective_loc_pct: number; margin_above_loc_pct: number;
}

/** A row of the curated database.
 *
 * `record_kind` is derived server-side (backend/engine/records.py): only
 * "experiment" rows are controlled combustion evidence; "historical" and
 * "specification" rows carry no combustion verdict and are shown as context.
 * `source_type` says whether `source_id` is an NTRS ID, a PMC ID, a journal
 * article ID or a NASA History slug — labelling every link "NTRS" would
 * misstate the provenance.
 */
export type RecordKind = "experiment" | "historical" | "specification" | "unspecified";

export interface Experiment {
  experiment_id: string; mission: string; platform: string; year: number;
  material: string; material_class: string; pressure_kpa: number; o2_pct: number;
  gravity: string; flow_ms: number; geometry: string; verdict: string;
  outcome_type: string; notes: string;
  source_type: string; source_id: string; source_url: string;
  record_kind: RecordKind; record_kind_label: string;
  similarity?: number;
}

export interface ScenarioResponse {
  inputs: Record<string, unknown>;
  hazard: HazardVector;
  evidence_label: string;
  coverage_pct: number;
  relevant_experiments: Experiment[];
  loc: { base_pct: number; effective_pct: number; margin_pct: number; flag: string };
}

export interface TradeSpaceResponse {
  p_psia: number[]; o2_pct: number[];
  grid: Array<Array<{
    ignition: number; spread: number; persistence: number;
    heat_release: number; extinction_margin: number; crew_safe: boolean;
  }>>;
  loc_boundary: Array<{ p_psia: number; loc_pct: number | null; flag: string }>;
  /** The same ignition field computed at 1g, for the Freefall Lab ghost
   * surface; null when the request already is 1g. Drawn BELOW the current
   * surface by height_offset_pct (ignition points). */
  ghost_grid_1g: Array<Array<{ ignition: number; height_offset_pct: number }>> | null;
  crew_band: { po2_min_psia: number; po2_max_psia: number };
  p_envelope_kpa: [number, number];
}

export interface MethodologyResponse {
  limitations: Array<{ id: string; title: string; detail: string }>;
  future_work: Array<{ id: string; title: string; detail: string }>;
  governance: string[];
  data_provenance: Array<{ claim: string; source: string }>;
  dossier_refs: string[];
}

export interface ValidationResponse {
  method: string; total: number; correct: number;
  accuracy: number | null; accuracy_non_anchor: number | null;
  results: Array<{
    experiment_id: string; mission: string; conditions: string;
    observed: string; predicted: string; margin_pct: number;
    is_fit_anchor: boolean; correct: boolean; explanation: string | null;
  }>;
}

export interface ParetoResponse {
  fire_weight: number;
  candidates: Array<{
    id: string; p: number; o2: number; fire_risk: number; eva: number;
    ignition: number; crew_safe: boolean; normoxia_pct: number;
    on_frontier: boolean; weighted_score: number;
  }>;
  recommended: string | null;
}

export interface AskResponse {
  question: string;
  /** Intent chosen by the deterministic router (backend/engine/intents.py). */
  intent: string;
  intent_matched: string[];
  intent_confidence: number;
  answer: string;
  citations: string[];
  context_citations: string[];
  context_kinds: Record<string, RecordKind>;
  suggested_questions: string[];
  fabricated_citations: string[];
  citation_check_ok: boolean;
  engine_summary: HazardVector;
  mode: string;
}

/** /api/flame — the geometry behind the Freefall Lab screen (dossier §4.2.1).
 *
 * Every visual claim the screen makes is one of these fields: the regime is a
 * cited published behaviour, the fate is the engine's own boundary decision, and
 * the crossover is computed from the same gravity offset the rest of the product
 * uses. Front speed is relative to the Saffire-I anchor, never m/s.
 */
export interface FlameResponse {
  hazard: HazardVector;
  regime: {
    shape: "teardrop" | "spherical";
    buoyant_convection: boolean;
    colour_tendency: string;
    style: "stable" | "transitional" | "flickering";
    label: string;
    note: string;
    citations: string[];
  };
  fate: {
    code: "sustained" | "marginal" | "self_extinguishing";
    label: string;
    detail: string;
  };
  /** Airflow rendering bands (FL2, qualitative). */
  flow_regime: { band: string; note: string; streamer_speed_scale: number };
  /** Cool-flame phase flag (FL4/FL5, qualitative — no cool-flame chemistry). */
  cool_flame_phase: {
    possible: boolean; label: string; note: string; citations: string[];
  };
  front_speed_relative: number;
  reference: {
    experiment_id: string;
    condition: string;
    spread_index: number;
    margin_above_loc_pct: number;
    note: string;
  };
  crossover: {
    pressure_psia: number;
    o2_pct: number[];
    series: Record<string, Array<{ o2_pct: number; margin_pct: number }>>;
    loc_pct: Record<string, number>;
    offset_pt: number;
    microgravity_sustains_below_1g_at_pct: number;
    published_finding: string;
    citation: string;
  };
  citations: Array<{ id: string; claim: string; source: string; url: string; kind: string }>;
  notes: string[];
}

/** /api/missions — real-hardware flight scenarios with engine-computed 1g twins. */
export interface MissionScenario {
  id: string; name: string; gravity: string;
  pressure_psia: number; o2_pct: number; flow_ms: number; temperature_c: number;
  material_class: string; context: string; provenance: string;
  evaluation: {
    hazard: HazardVector;
    effective_loc_pct: number; margin_above_loc_pct: number;
    twin_1g: {
      gravity: string; hazard: HazardVector;
      effective_loc_pct: number; margin_above_loc_pct: number;
    };
    delta_vs_1g: {
      margin_pt: number; ignition: number; spread: number; wording: string;
    };
  };
}

export interface MissionsResponse {
  scenarios: MissionScenario[];
  default_compare: { a: string; b: string };
  note: string;
}

export interface CounterfactualResponse {
  before: HazardVector; after: HazardVector;
  deltas: Record<string, number>; overall: string;
}

/** /api/countermoves — ranked, engine-computed fire-safety levers.
 *
 * Each lever's before/after summary is the engine's own vector projection; a
 * lever the model does not support in this regime comes back `applicable:
 * false` with the reason in `note`, never as a silent zero delta.
 */
export interface LeverVector {
  ignition: number; spread: number; persistence: number;
  heat_release: number; extinction_margin: number;
  margin_above_loc_pct: number;
  crew: { po2_psia: number; normoxia_pct: number; crew_safe: boolean };
}

export interface CountermovesLever {
  id: string; title: string; action: string; applicable: boolean;
  before: LeverVector; after: LeverVector;
  delta: { ignition: number; spread: number; margin_above_loc_pct: number };
  evidence_label: string; note: string;
}

export interface CountermovesResponse {
  inputs: Record<string, unknown>;
  baseline: LeverVector;
  levers: CountermovesLever[];
  ranked_ids: string[];
  notes: string[];
}

/** /api/design-search — the inverse of the trade-space question.
 *
 * Each row is one cabin pressure: the O2 fraction the crew's pO2 floor forces,
 * and the effective LOC boundary at that pressure. `window_pt` is the width of
 * the breathable band that is ALSO below the boundary (0 when the crew floor is
 * above it), and `status` says whether that band is usable, nominal (narrower
 * than the model's own uncertainty), or absent. `crossover_psia` is solved in
 * closed form server-side; the screen draws it, it does not compute it.
 */
export interface DesignSearchRow {
  pressure_psia: number;
  pressure_kpa: number;
  crew_floor_o2_pct: number;
  crew_ceiling_o2_pct: number;
  loc_pct: number;
  shortfall_pt: number;
  window_pt: number;
  ignition_at_floor: number;
  flag: "INTERPOLATED" | "EXTRAPOLATED";
  status: "usable_window" | "nominal_window" | "unavoidable_spread" | "outside_data";
}

export interface DesignSearchResponse {
  inputs: Record<string, number | string>;
  rows: DesignSearchRow[];
  crossover_psia: number | null;
  window: {
    min_psia: number; max_psia: number;
    inside_data_psia: [number, number] | null;
  } | null;
  best: DesignSearchRow;
  current: DesignSearchRow | null;
  verdict: "window_exists" | "no_window_in_range" | "no_fire_limit";
  statement: string;
  nominal_window_pt: number;
  notes: string[];
}

/** Human-readable source label: the ID means different registries per type. */
export function sourceLabel(e: Pick<Experiment, "source_type" | "source_id">): string {
  const kind =
    e.source_type === "ntrs" ? "NTRS"
    : e.source_type === "pmc" ? "PMC"
    : e.source_type === "publisher" ? "journal"
    : e.source_type === "nasa-history" ? "NASA History"
    : "source";
  return `${kind} ${e.source_id}`;
}

/** Query string for every endpoint that takes the full atmosphere state. */
export interface AtmosphereParams {
  pressure: number;
  o2: number;
  gravity: string;
  flow: number;
  temperature: number;
  material: string;
}

export function atmosphereQuery(p: AtmosphereParams): string {
  return (
    `pressure_psia=${p.pressure}&o2_pct=${p.o2}&gravity=${p.gravity}` +
    `&flow_ms=${p.flow}&temperature_c=${p.temperature}&material_class=${p.material}`
  );
}

/** URL of the Markdown decision memo for a state (download=true attaches it). */
export function reportUrl(p: AtmosphereParams, download = false): string {
  return `${BASE}/api/report?${atmosphereQuery(p)}&download=${download}`;
}

export const api = {
  scenario: (q: string) => get<ScenarioResponse>(`/api/scenario?${q}`),
  tradespace: (q: string) => get<TradeSpaceResponse>(`/api/tradespace?${q}`),
  experiments: (q: string) =>
    get<{ count: number; evidence_count: number; context_count: number; results: Experiment[] }>(
      `/api/experiments?${q}`,
    ),
  validate: () => get<ValidationResponse>("/api/validate"),
  pareto: (q: string) => get<ParetoResponse>(`/api/pareto?${q}`),
  ask: (body: Record<string, unknown>) => post<AskResponse>("/api/ask", body),
  methodology: () => get<MethodologyResponse>("/api/methodology"),
  flame: (q: string) => get<FlameResponse>(`/api/flame?${q}`),
  missions: () => get<MissionsResponse>("/api/missions"),
  counterfactual: (body: Record<string, unknown>) =>
    post<CounterfactualResponse>("/api/counterfactual", body),
  countermoves: (q: string) => get<CountermovesResponse>(`/api/countermoves?${q}`),
  designSearch: (q: string) => get<DesignSearchResponse>(`/api/design-search?${q}`),
};

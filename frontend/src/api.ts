// Typed FLARE API client.
const BASE = "http://localhost:8787";

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

export interface Experiment {
  experiment_id: string; mission: string; platform: string; year: number;
  material: string; material_class: string; pressure_kpa: number; o2_pct: number;
  gravity: string; flow_ms: number; geometry: string; verdict: string;
  outcome_type: string; notes: string; ntrs_id: string; source_url: string;
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
  crew_band: { po2_min_psia: number; po2_max_psia: number };
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
  answer: string; citations: string[]; fabricated_citations: string[];
  citation_check_ok: boolean; engine_summary: HazardVector; mode: string;
}

export interface CounterfactualResponse {
  before: HazardVector; after: HazardVector;
  deltas: Record<string, number>; overall: string;
}

export const api = {
  scenario: (q: string) => get<ScenarioResponse>(`/api/scenario?${q}`),
  tradespace: (q: string) => get<TradeSpaceResponse>(`/api/tradespace?${q}`),
  experiments: (q: string) => get<{ count: number; results: Experiment[] }>(`/api/experiments?${q}`),
  validate: () => get<ValidationResponse>("/api/validate"),
  pareto: (q: string) => get<ParetoResponse>(`/api/pareto?${q}`),
  ask: (body: Record<string, unknown>) => post<AskResponse>("/api/ask", body),
  counterfactual: (body: Record<string, unknown>) => post<CounterfactualResponse>("/api/counterfactual", body),
};

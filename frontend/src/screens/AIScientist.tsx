import { useState } from "react";
import { api, type AskResponse, type CounterfactualResponse } from "../api";

export default function AIScientist({ query }: { query: string }) {
  const [question, setQuestion] = useState("Why is 34% O2 riskier than 28% at the same pressure?");
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [cf, setCf] = useState<CounterfactualResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // The full app state, temperature included, so an answer cannot describe a
  // different atmosphere than the sliders show.
  const params = new URLSearchParams(query);
  const body = {
    question,
    pressure_psia: +params.get("pressure_psia")!,
    o2_pct: +params.get("o2_pct")!,
    gravity: params.get("gravity")!,
    flow_ms: +params.get("flow_ms")!,
    temperature_c: +params.get("temperature_c")!,
    material_class: params.get("material_class")!,
  };

  async function run() {
    setBusy(true); setErr(null);
    try {
      setAnswer(await api.ask(body));
    } catch (e) { setErr(String(e)); }
    setBusy(false);
  }

  async function counterfactual(dO2: number, dFlow: number) {
    setBusy(true); setErr(null);
    try {
      setCf(await api.counterfactual({ ...body, delta_o2_pct: dO2, delta_flow_ms: dFlow }));
    } catch (e) { setErr(String(e)); }
    setBusy(false);
  }

  return (
    <div className="grid lg:grid-cols-[1fr_320px] gap-4">
      <div className="space-y-4">
        <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
          <div className="flex gap-2">
            <input className="flex-1 bg-slate-800 border border-slate-700 rounded px-3 py-2 text-sm"
              value={question} onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && run()}
              placeholder="Ask about this atmosphere…" />
            <button onClick={run} disabled={busy}
              className="bg-orange-600 hover:bg-orange-500 disabled:opacity-50 rounded px-4 py-2 text-sm font-semibold">
              {busy ? "…" : "Ask"}
            </button>
          </div>
          <p className="text-[11px] text-slate-500 mt-2">
            Answers are composed from the deterministic engine + curated NASA experiment database.
            Every cited experiment ID is verified against the database in code — fabricated citations are flagged, never shown.
          </p>
          <p className="text-[11px] text-amber-500/80 mt-1">
            The question text is recorded and echoed back; because no language model is called in
            this build, the answer is composed from the current atmosphere and cited experiments
            rather than parsed out of the question (see Methodology → F4).
          </p>
        </div>

        {err && <div className="text-red-300 text-sm">Error: {err}</div>}

        {answer && (
          <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4 space-y-3">
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-500">mode:</span>
              <span className="font-mono text-slate-300">{answer.mode}</span>
              <span className={`ml-auto px-2 py-0.5 rounded border font-mono text-[10px] ${
                answer.citation_check_ok
                  ? "bg-emerald-900/60 text-emerald-300 border-emerald-700"
                  : "bg-red-900/60 text-red-300 border-red-700"}`}>
                {answer.citation_check_ok ? "citations verified ✓" : `fabricated caught: ${answer.fabricated_citations.join(", ")}`}
              </span>
            </div>
            <div className="text-[11px] text-slate-500">
              question recorded: <span className="text-slate-300">{answer.question}</span>
            </div>
            <pre className="whitespace-pre-wrap text-sm text-slate-200 font-sans">{answer.answer}</pre>
            <div className="flex flex-wrap gap-2">
              {answer.citations.map((c) => (
                <button key={c}
                  onClick={() => {
                    const el = document.getElementById(`exp-${c}`);
                    if (el) { el.scrollIntoView({ behavior: "smooth" }); el.classList.add("ring", "ring-orange-500"); setTimeout(() => el.classList.remove("ring", "ring-orange-500"), 2000); }
                  }}
                  className="text-[11px] font-mono bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sky-300">
                  📄 {c}
                </button>
              ))}
            </div>
          </div>
        )}

        {cf && (
          <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-sm">Counterfactual result</h3>
              <span className={`text-xs font-mono px-2 py-0.5 rounded ${cf.overall === "WORSE" ? "bg-red-900/60 text-red-300" : "bg-emerald-900/60 text-emerald-300"}`}>
                overall {cf.overall}
              </span>
            </div>
            <table className="w-full text-xs">
              <thead><tr className="text-slate-500 text-left">
                <th className="py-1">Component</th><th>Before</th><th>After</th><th>Δ</th>
              </tr></thead>
              <tbody className="font-mono">
                {(["ignition", "spread", "persistence", "heat_release", "extinction_margin"] as const).map((k) => (
                  <tr key={k} className="border-t border-slate-800">
                    <td className="py-1 font-sans text-slate-300">{k.replace("_", " ")}</td>
                    <td>{cf.before[k].toFixed(1)}</td>
                    <td>{cf.after[k].toFixed(1)}</td>
                    <td className={cf.deltas[k] > 0 ? "text-red-300" : cf.deltas[k] < 0 ? "text-emerald-300" : ""}>
                      {cf.deltas[k] > 0 ? "+" : ""}{cf.deltas[k].toFixed(1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4 h-fit">
        <h3 className="font-semibold text-sm mb-2">Counterfactuals</h3>
        <p className="text-[11px] text-slate-500 mb-3">Ask the engine "what if" — deltas are computed by re-running the deterministic model, not by the AI.</p>
        <div className="space-y-2">
          <button onClick={() => counterfactual(2, 0)} disabled={busy}
            className="w-full bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded px-3 py-2 text-sm text-left">
            🔺 What if O₂ increases by 2%?
          </button>
          <button onClick={() => counterfactual(-2, 0)} disabled={busy}
            className="w-full bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded px-3 py-2 text-sm text-left">
            🔻 What if O₂ decreases by 2%?
          </button>
          <button onClick={() => counterfactual(0, -0.15)} disabled={busy}
            className="w-full bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded px-3 py-2 text-sm text-left">
            💨 What if airflow drops by 0.15 m/s?
          </button>
          <button onClick={() => counterfactual(0, 0.15)} disabled={busy}
            className="w-full bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded px-3 py-2 text-sm text-left">
            💨 What if airflow rises by 0.15 m/s?
          </button>
        </div>
      </div>
    </div>
  );
}

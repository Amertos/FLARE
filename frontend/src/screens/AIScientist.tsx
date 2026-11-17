import { useState } from "react";
import { api, type AskResponse, type CounterfactualResponse } from "../api";
import { ScreenHeader, FlarePanel } from "../ui/FlarePanel";

const STARTERS = [
  "Why is 34% O2 riskier than 28% at the same pressure?",
  "Which experiments support this atmosphere?",
  "What if airflow drops to 0.05 m/s?",
  "What pressure makes this atmosphere non-flammable?",
  "How accurate is the model on held-out experiments?",
];

export default function AIScientist({ query, onCite }: {
  query: string;
  onCite: (experimentId: string) => void;
}) {
  const [question, setQuestion] = useState(STARTERS[0]);
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

  async function run(asked = question) {
    setBusy(true); setErr(null);
    try {
      setAnswer(await api.ask({ ...body, question: asked }));
      setQuestion(asked);
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
    <div className="screen-enter">
      <ScreenHeader
        eyebrow="Screen 6 · The question"
        title="Ask FLARE"
        lede="Questions are routed by an explicit keyword model into intents, and the intent decides which engine quantities the answer reports. No language model is called anywhere in this build — answers are composed from the deterministic engine, and every cited experiment is verified against the database in code."
      />

      <div className="grid lg:grid-cols-[1fr_320px] gap-4 mt-3">
      <div className="space-y-4">
        <FlarePanel title="Question console" hint="deterministic router · no LLM">
          <div className="flex gap-2">
            <label className="flex-1">
              <span className="sr-only">Ask about this atmosphere</span>
              <input className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-sm"
                value={question} onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && run()}
                placeholder="Ask about this atmosphere…" />
            </label>
            <button onClick={() => run()} disabled={busy}
              className="bg-orange-600 hover:bg-orange-500 disabled:opacity-50 rounded px-4 py-2 text-sm font-semibold">
              {busy ? "…" : "Ask"}
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {STARTERS.map((s) => (
              <button key={s} onClick={() => run(s)} disabled={busy}
                className="text-[11px] px-2 py-1 rounded border border-slate-700 bg-slate-800/60 hover:bg-slate-700 text-slate-300 disabled:opacity-50">
                {s}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-slate-500 mt-2">
            A question outside the engine's scope is answered as out of scope rather than narrated.
          </p>
        </FlarePanel>

        {err && <div className="text-red-300 text-sm" role="alert">Error: {err}</div>}

        {answer && (
          <FlarePanel title="Answer" headerExtra={null}>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="text-slate-500">route:</span>
              <span className="font-mono text-orange-300 border border-orange-900/70 bg-orange-950/40 rounded px-1.5 py-0.5">
                {answer.intent}
              </span>
              {answer.intent_matched.length > 0 && (
                <span className="text-slate-500 font-mono text-[11px]">
                  matched “{answer.intent_matched.join("”, “")}” · confidence {answer.intent_confidence}
                </span>
              )}
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

            {answer.citations.length > 0 && (
              <div>
                <div className="text-[11px] text-slate-500 mb-1">
                  Supporting evidence — controlled experiments. Click to open the record:
                </div>
                <div className="flex flex-wrap gap-2">
                  {answer.citations.map((c) => (
                    <button key={c} onClick={() => onCite(c)}
                      className="text-[11px] font-mono bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded px-2 py-1 text-sky-300">
                      📄 {c}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {answer.context_citations.length > 0 && (
              <div>
                <div className="text-[11px] text-slate-500 mb-1">
                  Context records — nearest rows that carry no combustion verdict, so they are not
                  counted as fire evidence:
                </div>
                <div className="flex flex-wrap gap-2">
                  {answer.context_citations.map((c) => (
                    <button key={c} onClick={() => onCite(c)}
                      title={answer.context_kinds[c]}
                      className="text-[11px] font-mono bg-slate-800/60 hover:bg-slate-700 border border-amber-900/60 rounded px-2 py-1 text-amber-300">
                      🏷️ {c} <span className="text-slate-500">({answer.context_kinds[c]})</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {answer.suggested_questions.length > 0 && (
              <div className="pt-1 border-t border-slate-800">
                <div className="text-[11px] text-slate-500 mb-1">Follow-ups the engine can answer:</div>
                <div className="flex flex-wrap gap-1.5">
                  {answer.suggested_questions.map((s) => (
                    <button key={s} onClick={() => run(s)} disabled={busy}
                      className="text-[11px] px-2 py-1 rounded border border-slate-700 hover:bg-slate-700 text-slate-300 disabled:opacity-50">
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </FlarePanel>
        )}

        {cf && (
          <FlarePanel
            title="Counterfactual result"
            headerExtra={
              <span className={`text-xs font-mono px-2 py-0.5 rounded ${cf.overall === "WORSE" ? "bg-red-900/60 text-red-300" : "bg-emerald-900/60 text-emerald-300"}`}>
                overall {cf.overall}
              </span>
            }
          >
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
          </FlarePanel>
        )}
      </div>

      <FlarePanel title="Counterfactuals" className="h-fit">
        <p className="text-[11px] text-slate-500 mb-3">
          Ask the engine “what if” — deltas are computed by re-running the deterministic model,
          not by a language model.
        </p>
        <div className="space-y-2">
          <button onClick={() => counterfactual(2, 0)} disabled={busy}
            className="w-full bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded px-3 py-2 text-sm text-left disabled:opacity-50">
            🔺 What if O₂ increases by 2%?
          </button>
          <button onClick={() => counterfactual(-2, 0)} disabled={busy}
            className="w-full bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded px-3 py-2 text-sm text-left disabled:opacity-50">
            🔻 What if O₂ decreases by 2%?
          </button>
          <button onClick={() => counterfactual(0, -0.15)} disabled={busy}
            className="w-full bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded px-3 py-2 text-sm text-left disabled:opacity-50">
            💨 What if airflow drops by 0.15 m/s?
          </button>
          <button onClick={() => counterfactual(0, 0.15)} disabled={busy}
            className="w-full bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded px-3 py-2 text-sm text-left disabled:opacity-50">
            💨 What if airflow rises by 0.15 m/s?
          </button>
        </div>
        <p className="text-[11px] text-slate-500 mt-3">
          Counterfactual deltas rank atmospheres relative to each other. They are not absolute risk
          and they inherit every limitation listed on the Methodology screen.
        </p>
      </FlarePanel>
      </div>
    </div>
  );
}

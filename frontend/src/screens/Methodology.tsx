import { useEffect, useState } from "react";
import { api, type MethodologyResponse } from "../api";
import { ScreenHeader, FlarePanel } from "../ui/FlarePanel";

function Section({
  title,
  subtitle,
  count,
  children,
}: {
  title: string;
  subtitle?: string;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <FlarePanel
      title={title}
      hint={count !== undefined ? String(count) : undefined}
    >
      {subtitle && <p className="text-[11px] text-slate-500 mb-3">{subtitle}</p>}
      <div className="space-y-2">{children}</div>
    </FlarePanel>
  );
}

export default function Methodology() {
  const [data, setData] = useState<MethodologyResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .methodology()
      .then((d) => alive && setData(d))
      .catch((e) => alive && setErr(String(e)));
    return () => {
      alive = false;
    };
  }, []);

  if (err) return <div className="text-red-300 text-sm">Backend unreachable ({err}).</div>;
  if (!data) return <div className="text-slate-400 text-sm p-6">Loading methodology…</div>;

  return (
    <div className="space-y-4 screen-enter">
      <ScreenHeader
        eyebrow="Screen 8 · The ledger"
        title="Methodology — what FLARE does not claim"
        lede="FLARE is a decision-support tool. It never states which atmosphere is best, never issues an operational command, and does not colour a single pixel where NASA has no measurement. Everything on this screen is served by the engine (/api/methodology) so the product and the written record cannot drift apart."
      />

      <p className="text-[11px] text-slate-500 font-mono -mt-2">{data.dossier_refs.join("  ·  ")}</p>

      <Section
        title="Known limitations"
        subtitle="Carried verbatim in substance from the validation dossier §4.7. Read these before trusting any number."
        count={data.limitations.length}
      >
        {data.limitations.map((l) => (
          <div key={l.id} className="border border-slate-800 rounded p-3 bg-slate-950/40">
            <div className="flex items-baseline gap-2">
              <span className="text-[10px] font-mono text-orange-400 border border-orange-900/70 bg-orange-950/40 rounded px-1.5 py-0.5">
                {l.id}
              </span>
              <span className="text-sm font-medium text-slate-200">{l.title}</span>
            </div>
            <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">{l.detail}</p>
          </div>
        ))}
      </Section>

      <Section
        title="Not built in this version"
        subtitle="Stated explicitly so the interface never implies capability the build does not have."
        count={data.future_work.length}
      >
        {data.future_work.map((f) => (
          <div key={f.id} className="border border-slate-800 rounded p-3 bg-slate-950/40">
            <div className="flex items-baseline gap-2">
              <span className="text-[10px] font-mono text-sky-400 border border-sky-900/70 bg-sky-950/40 rounded px-1.5 py-0.5">
                {f.id}
              </span>
              <span className="text-sm font-medium text-slate-200">{f.title}</span>
            </div>
            <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">{f.detail}</p>
          </div>
        ))}
      </Section>

      <div className="grid lg:grid-cols-2 gap-4">
        <Section title="Model governance" subtitle="Rules enforced in code, not by convention.">
          <ul className="space-y-2">
            {data.governance.map((g, i) => (
              <li key={i} className="text-xs text-slate-300 flex gap-2">
                <span className="text-emerald-400 shrink-0">✓</span>
                <span className="leading-relaxed">{g}</span>
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Evidence labels" subtitle="Computed from the database at request time — never assigned by hand.">
          <div className="space-y-2 text-xs">
            <div className="flex gap-2">
              <span className="shrink-0 px-2 py-0.5 rounded border font-mono text-[10px] bg-emerald-900/60 text-emerald-300 border-emerald-700">
                OBSERVED
              </span>
              <span className="text-slate-400">An experiment exists within tolerance on pressure, O₂, gravity regime and material class.</span>
            </div>
            <div className="flex gap-2">
              <span className="shrink-0 px-2 py-0.5 rounded border font-mono text-[10px] bg-amber-900/60 text-amber-300 border-amber-700">
                INTERPOLATED
              </span>
              <span className="text-slate-400">The query sits inside the experimental envelope on every axis, but no record matches directly.</span>
            </div>
            <div className="flex gap-2">
              <span className="shrink-0 px-2 py-0.5 rounded border font-mono text-[10px] bg-orange-900/60 text-orange-300 border-orange-700">
                EXTRAPOLATED
              </span>
              <span className="text-slate-400">The query lies outside the envelope on an axis. The Trade Space hatches these regions instead of colouring them.</span>
            </div>
            <div className="flex gap-2">
              <span className="shrink-0 px-2 py-0.5 rounded border font-mono text-[10px] bg-red-900/60 text-red-300 border-red-700">
                INSUFFICIENT
              </span>
              <span className="text-slate-400">Fewer than two compatible records in the neighbourhood. The engine reports the gap rather than filling it.</span>
            </div>
          </div>
        </Section>
      </div>

      <Section
        title="Data provenance"
        subtitle="Every load-bearing claim and the source it was verified against."
        count={data.data_provenance.length}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-500 text-left">
                <th className="py-1 pr-4 font-medium">Claim used by FLARE</th>
                <th className="font-medium">Source</th>
              </tr>
            </thead>
            <tbody>
              {data.data_provenance.map((p, i) => (
                <tr key={i} className="border-t border-slate-800">
                  <td className="py-1.5 pr-4 text-slate-300 align-top">{p.claim}</td>
                  <td className="py-1.5 text-slate-400 align-top">{p.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}

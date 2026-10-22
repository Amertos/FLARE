/** Shared chrome for the FLARE console: the panel shell every card uses and
 *  the intro block that opens every screen. Centralising them is what makes
 *  six independent screens read as one product.
 *
 *  Panels keep the CSS-side `.panel` surface (index.css) and add a title row:
 *  a corner accent glyph, the title, and an optional right-aligned hint. */

export function FlarePanel({
  title,
  hint,
  children,
  className = "",
  headerExtra,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
  className?: string;
  /** Extra right-aligned content that is richer than a plain hint (e.g. a
   *  flag chip). When present it replaces `hint`. */
  headerExtra?: React.ReactNode;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="flex items-center gap-2 mb-3">
        <span className="corner-mark shrink-0" aria-hidden="true" />
        <h2 className="panel-title">{title}</h2>
        {headerExtra ?? (hint ? <span className="panel-hint">{hint}</span> : null)}
      </div>
      {children}
    </section>
  );
}

/** The intro block at the top of each screen: eyebrow, one-line title, and
 *  the lede paragraph. Same rhythm on all six screens. */
export function ScreenHeader({
  eyebrow,
  title,
  lede,
  aside,
}: {
  eyebrow: string;
  title: string;
  lede: string;
  /** Right-aligned extras (flag chips, jump selects) — laid out by the caller. */
  aside?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2 mb-1">
      <div className="min-w-0">
        <div className="eyebrow mb-1">{eyebrow}</div>
        <h1 className="masthead-title text-lg sm:text-xl font-bold tracking-tight text-slate-100">
          {title}
        </h1>
        <p className="screen-lede mt-1.5">{lede}</p>
      </div>
      {aside && <div className="shrink-0">{aside}</div>}
    </div>
  );
}

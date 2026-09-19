import { useId, useState } from "react";
import {
  OUTLOOK_CATEGORIES, outlookLabel, outlookTone, initialOutlookCategory, selectOutlookCategory,
  categoryIntroduction, categorySources, industryMeasurements, formatReturn, formatRelative,
} from "../utils/outlookPresentation";

const SYMBOLS = { positive: "↑", negative: "↓", mixed: "↔", muted: "–", immaterial: "○" };
function Status({ label }) {
  const tone = outlookTone(label);
  return <span className={`outlook-status outlook-status--${tone}`}>
    <span aria-hidden="true">{SYMBOLS[tone]}</span> {label}
  </span>;
}
function EvidenceExplanation({ category, factor }) {
  const measurement = industryMeasurements(category, factor);
  if (measurement?.kind === "breadth") {
    const d = measurement.details;
    return <>
      <div className="outlook-measurements">
        <p><strong>{Math.round(d.positive_return_breadth * 100)}%</strong> positive over 21 sessions</p>
        <p><strong>{Math.round(d.above_sma50_breadth * 100)}%</strong> above the 50-session average</p>
      </div>
      <p className="outlook-evidence-note">Sector sample · Coverage: {d.peer_coverage}/{d.peer_sample.length} peers</p>
    </>;
  }
  if (measurement?.kind === "performance") {
    const d = measurement.details;
    return <table className="outlook-performance">
      <caption className="outlook-sr-only">Sector returns and relative performance in percentage points</caption>
      <thead><tr><th scope="col">Sessions</th><th scope="col">{d.benchmark}</th><th scope="col">vs {d.market_benchmark}</th></tr></thead>
      <tbody>{[21, 63].map((days) => <tr key={days}>
        <th scope="row">{days}</th><td>{formatReturn(d[`return_${days}`])}</td><td>{formatRelative(d[`relative_${days}`])}</td>
      </tr>)}</tbody>
    </table>;
  }
  return <p className="outlook-evidence-explanation">{factor.description || "See the source observations below."}</p>;
}
function Sources({ sources, name }) {
  return sources.length > 0 && <div className="outlook-sources" aria-label={`${OUTLOOK_CATEGORIES[name]} sources`}>
    <span>Sources</span>
    <ul>{sources.map((source, index) => <li key={`${source.url}-${index}`}>
      {source.url ? <a href={source.url} target="_blank" rel="noopener noreferrer">{source.name}</a> : source.name}
    </li>)}</ul>
  </div>;
}
function CategoryDetails({ name, category }) {
  const factors = category?.status === "available" ? category.factors || [] : [];
  const evidence = category?.evidence || [];
  const sources = categorySources(category);
  return <>
    <div className="outlook-detail-heading"><h4>{OUTLOOK_CATEGORIES[name]}</h4><Status label={outlookLabel(category)} /></div>
    <p className="outlook-detail-intro">{categoryIntroduction(name, category)}</p>
    {factors.length > 0 && <ul className="outlook-evidence-list">
      {factors.map((factor, index) => <li className="outlook-evidence-row" key={`${factor.title}-${index}`}>
        <div className="outlook-evidence-heading"><h5>{factor.title}</h5>{factor.impact && <Status label={factor.impact} />}</div>
        <EvidenceExplanation category={category} factor={factor} />
      </li>)}
    </ul>}
    {category?.status === "available" && <Sources sources={sources} name={name} />}
    {(category?.summary || factors.length > 0 || evidence.length > 0) && <details className="outlook-methodology">
      <summary>Full evidence &amp; methodology</summary>
      {category.status !== "available" && <Sources sources={sources} name={name} />}
      {category.summary && <p>{category.summary}</p>}
      {category.status !== "available" && evidence.length > 0 && <p>Source observations below do not establish a category assessment.</p>}
      {factors.filter((factor) => !evidence.some((item) => item.summary === factor.description))
        .map((factor, index) => <div key={`factor-${index}`}><h5>{factor.title}</h5><p>{factor.description}</p></div>)}
      {evidence.map((item, index) => <div key={item.id || index} className="outlook-source-observation">
        <h5>{item.title || "Source observation"}</h5><p>{item.summary}</p>
        <p className="outlook-evidence-note">{item.source}{item.published_at ? ` · Published ${item.published_at.slice(0, 10)}` : ""}</p>
        {(item.exposure_links || []).map((link, i) => <p key={i}>{link.description}</p>)}
      </div>)}
    </details>}
  </>;
}
export function OutlookCategories({ categories, disabled = false, loading = false }) {
  const [selected, setSelected] = useState(() => initialOutlookCategory(categories));
  const id = useId();
  return <>
    <div className="outlook-category-grid" role="group" aria-label="Outlook categories">
      {Object.entries(OUTLOOK_CATEGORIES).map(([key, name]) => <button
        type="button" key={key} id={`${id}-${key}`} className="outlook-category-button"
        aria-pressed={selected === key} aria-expanded={selected === key} aria-controls={`${id}-detail`}
        disabled={disabled} onClick={() => setSelected((current) => selectOutlookCategory(current, key))}>
        <span className="outlook-category-name">{name}</span>
        <Status label={loading ? "Loading…" : outlookLabel(categories?.[key])} />
      </button>)}
    </div>
    <div id={`${id}-detail`} hidden={!selected || disabled}>
      {selected && !disabled && <section className="outlook-detail" aria-labelledby={`${id}-${selected}`} key={selected}>
        <CategoryDetails name={selected} category={categories?.[selected]} />
      </section>}
    </div>
  </>;
}
export default function OutlookPanel({ data, loading = false, error = "", embedded = false }) {
  const id = useId();
  const label = loading ? "Loading…" : error ? "Temporarily unavailable" : outlookLabel(data);
  const hasCategories = !loading && !error && data?.categories && typeof data.categories === "object";
  const message = loading ? "Loading Outlook…" : error ? "Outlook is temporarily unavailable. Please try again later."
    : !data ? "Outlook data is unavailable." : data.metadata?.uses_placeholder_data ? "Preview · Intelligence not connected"
    : data.status === "error" ? "Outlook context is temporarily unavailable. Please try again later."
    : data.status === "unavailable" ? "There is not enough available context for an overall assessment." : null;
  return <section className={`${embedded ? "analysis-section" : "panel-box"} outlook-card`} aria-busy={loading} aria-labelledby={`${id}-heading`}>
    <header className="outlook-header">
      <div className="outlook-title-row"><h3 id={`${id}-heading`}>Outlook</h3><Status label={label} /></div>
      <p className="outlook-subtitle">External conditions affecting this stock</p>
      <div className="outlook-header-context">
        {!loading && !error && !data?.metadata?.uses_placeholder_data && Number.isInteger(data?.available_categories) &&
          <p className="outlook-coverage">{data.available_categories} of 6 categories available</p>}
        {message && <p className="outlook-message" role="status">{message}</p>}
      </div>
    </header>
    <OutlookCategories key={`${data?.ticker || "outlook"}-${hasCategories ? "ready" : "pending"}`}
      categories={hasCategories ? data.categories : {}} disabled={!hasCategories} loading={loading} />
    <p className="outlook-context-note">External context, not a trading recommendation.</p>
  </section>;
}

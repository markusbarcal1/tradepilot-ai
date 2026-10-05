import { useId, useState } from "react";
import OutlookEvents from "./OutlookEvents";
import { OUTLOOK_CATEGORIES, outlookLabel, outlookTone, initialOutlookCategory,
  selectOutlookCategory, categoryIntroduction, categorySources } from "../utils/outlookPresentation";

const SYMBOLS = { positive: "↑", negative: "↓", mixed: "↔", muted: "–", immaterial: "○" };
const DRIVER_SYMBOLS = { positive: "↑", negative: "↓", neutral: "↔", mixed: "↔" };
function Status({ label }) {
  const tone = outlookTone(label);
  return <span className={`outlook-status outlook-status--${tone}`}><span aria-hidden="true">{SYMBOLS[tone]}</span> {label}</span>;
}
function fallbackIntelligence(name, category) {
  return { category: name, availability: category?.status || "unavailable", rating: category?.label || null,
    summary: categoryIntroduction(name, category), positive_drivers: [], negative_drivers: [],
    neutral_mixed_drivers: [], important_metrics: [], sources: categorySources(category),
    evidence_sufficiency: category?.summary || "No evidence is available.", omitted_driver_count: 0 };
}
function allDrivers(intelligence) {
  return [...(intelligence?.positive_drivers || []), ...(intelligence?.negative_drivers || []),
    ...(intelligence?.neutral_mixed_drivers || [])];
}
function Driver({ driver, compact = false }) {
  const content = <><span aria-hidden="true">{DRIVER_SYMBOLS[driver.direction]}</span><span>{driver.label}</span>
    {(driver.change || driver.value) && <strong>{driver.change || driver.value}</strong>}
    {!compact && driver.importance && <small>{driver.importance} importance</small>}</>;
  return compact ? <span className={`outlook-driver outlook-driver--${driver.direction}`}>{content}</span>
    : <li className={`outlook-driver outlook-driver--${driver.direction}`}>
      {content}</li>;
}
function Sources({ intelligence, category, name }) {
  const sources = intelligence?.sources?.length ? intelligence.sources.map((source) => ({ name: source.name, url: source.url })) : categorySources(category);
  return sources.length > 0 && <div className="outlook-sources" aria-label={`${OUTLOOK_CATEGORIES[name]} sources`}><span>Sources</span>
    <ul>{sources.map((source, index) => <li key={`${source.url}-${index}`}>{source.url
      ? <a href={source.url} target="_blank" rel="noopener noreferrer">{source.name}</a> : source.name}</li>)}</ul></div>;
}
function Metric({ metric }) {
  const comparable = metric.expected || metric.previous;
  const direction = ["Beat", "Improved"].includes(metric.indicator) ? "positive" : ["Miss", "Declined"].includes(metric.indicator) ? "negative" : "neutral";
  return <li className="outlook-metric"><div className="outlook-metric-heading"><strong>{metric.label}</strong>
    {metric.indicator && <span className={`outlook-driver--${direction}`}>{DRIVER_SYMBOLS[direction]} {metric.indicator}</span>}</div>
    <dl>{metric.expected && <><dt>Expected</dt><dd>{metric.expected}</dd></>}{metric.previous && <><dt>Previous</dt><dd>{metric.previous}</dd></>}
      {metric.actual && <><dt>{comparable ? "Actual" : "Reported"}</dt><dd>{metric.actual}</dd></>}{metric.result && <><dt>Change</dt><dd>{metric.result}</dd></>}</dl>
    {!comparable && <p className="outlook-evidence-note">Comparison unavailable</p>}</li>;
}
function EventSummary({ title, event }) {
  if (!event) return null;
  const date = event.event_date ? new Date(`${event.event_date}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }) : null;
  return <div className="outlook-material-event"><h5>{title}</h5><p><strong>{event.title}</strong>{date ? ` · ${date}` : ""}</p>
    <p className="outlook-evidence-note">{event.importance.toUpperCase()} IMPACT{event.timing ? ` · ${event.timing}` : ""}{event.certainty ? ` · ${event.certainty}` : ""}</p></div>;
}
function CategoryDetails({ name, category, intelligence }) {
  const drivers = allDrivers(intelligence), evidence = category?.evidence || [];
  return <><div className="outlook-detail-heading"><h4>{OUTLOOK_CATEGORIES[name]}</h4><Status label={outlookLabel(category)} /></div>
    <p className="outlook-detail-intro">{intelligence.summary || categoryIntroduction(name, category)}</p>
    {intelligence.important_metrics?.length > 0 && <><h5 className="outlook-section-label">Important metrics</h5>
      <ul className="outlook-metric-grid">{intelligence.important_metrics.map((metric) => <Metric metric={metric} key={metric.key} />)}</ul></>}
    <h5 className="outlook-section-label">Why this rating</h5>
    {drivers.length > 0 ? <ul className="outlook-driver-list">{drivers.map((driver, index) => <Driver driver={driver} key={`${driver.label}-${index}`} />)}</ul>
      : <p className="outlook-detail-intro">{intelligence.evidence_sufficiency}</p>}
    {intelligence.omitted_driver_count > 0 && <p className="outlook-evidence-note">{intelligence.omitted_driver_count} lower-priority driver{intelligence.omitted_driver_count === 1 ? "" : "s"} omitted.</p>}
    <EventSummary title="Latest material event" event={intelligence.latest_material_event} /><EventSummary title="Next material event" event={intelligence.next_material_event} />
    {(category?.summary || evidence.length > 0 || intelligence.sources?.length > 0) && <details className="outlook-methodology"><summary>Sources &amp; methodology</summary>
      <p>{intelligence.evidence_sufficiency}</p><Sources intelligence={intelligence} category={category} name={name} />
      {evidence.map((item, index) => <div key={item.id || index} className="outlook-source-observation"><h5>{item.title || "Source observation"}</h5><p>{item.summary}</p>
        <p className="outlook-evidence-note">{item.source}{item.published_at ? ` · Published ${item.published_at.slice(0, 10)}` : ""}</p>
        {(item.exposure_links || []).map((link, i) => <p key={i}>{link.description}</p>)}</div>)}</details>}
  </>;
}
export function OutlookCategories({ categories, intelligence = {}, disabled = false, loading = false }) {
  const [selected, setSelected] = useState(() => initialOutlookCategory(categories)), id = useId();
  return <><div className="outlook-category-grid" role="group" aria-label="Outlook categories">
    {Object.entries(OUTLOOK_CATEGORIES).map(([key, name]) => { const category = categories?.[key], summary = intelligence?.[key] || fallbackIntelligence(key, category), drivers = allDrivers(summary);
      return <button type="button" key={key} id={`${id}-${key}`} className="outlook-category-button" aria-pressed={selected === key} aria-expanded={selected === key}
        aria-controls={`${id}-detail`} disabled={disabled} onClick={() => setSelected((current) => selectOutlookCategory(current, key))}>
        <span className="outlook-category-heading"><span className="outlook-category-name">{name}</span><Status label={loading ? "Loading…" : outlookLabel(category)} /></span>
        {drivers.slice(0, 3).map((driver, index) => <Driver driver={driver} compact key={`${driver.label}-${index}`} />)}
        {!loading && drivers.length === 0 && <span className="outlook-category-empty">{summary.summary}</span>}
      </button>; })}</div>
    <div id={`${id}-detail`} hidden={!selected || disabled}>{selected && !disabled && <section className="outlook-detail" aria-labelledby={`${id}-${selected}`} key={selected}>
      <CategoryDetails name={selected} category={categories?.[selected]} intelligence={intelligence?.[selected] || fallbackIntelligence(selected, categories?.[selected])} />
    </section>}</div></>;
}
function CompactEvents({ events }) {
  const upcoming = events || [];
  if (!upcoming.length) return null;
  return <section className="outlook-key-events" aria-label="Upcoming key events"><h4>Upcoming</h4><ul>{upcoming.map((event) =>
    <li key={event.event_id}><time>{event.event_date ? new Date(`${event.event_date}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" }) : "TBD"}</time>
      <span>{event.title}</span><strong>{event.importance.toUpperCase()} IMPACT</strong></li>)}</ul></section>;
}
export default function OutlookPanel({ data, loading = false, error = "", embedded = false }) {
  const id = useId(), label = loading ? "Loading…" : error ? "Temporarily unavailable" : outlookLabel(data);
  const hasCategories = !loading && !error && data?.categories && typeof data.categories === "object";
  const message = loading ? "Loading Outlook…" : error ? "Outlook is temporarily unavailable. Please try again later." : !data ? "Outlook data is unavailable."
    : data.metadata?.uses_placeholder_data ? "Preview · Intelligence not connected" : data.status === "error" ? "Outlook context is temporarily unavailable. Please try again later."
    : data.status === "unavailable" ? "There is not enough available context for an overall assessment." : null;
  const hasEvents = !loading && !error && (data?.event_intelligence?.upcoming?.length || data?.event_intelligence?.recent?.length);
  return <section className={`${embedded ? "analysis-section" : "panel-box"} outlook-card`} aria-busy={loading} aria-labelledby={`${id}-heading`}><header className="outlook-header">
    <div className="outlook-title-row"><h3 id={`${id}-heading`}>Overall Outlook</h3><Status label={label} /></div><p className="outlook-subtitle">External conditions affecting this stock</p>
    <div className="outlook-header-context">{!loading && !error && !data?.metadata?.uses_placeholder_data && Number.isInteger(data?.available_categories) && <p className="outlook-coverage">{data.available_categories} of 6 categories available</p>}
      {message && <p className="outlook-message" role="status">{message}</p>}</div></header>
    <OutlookCategories key={`${data?.ticker || "outlook"}-${hasCategories ? "ready" : "pending"}`} categories={hasCategories ? data.categories : {}}
      intelligence={hasCategories ? data.category_intelligence : {}} disabled={!hasCategories} loading={loading} />
    {!loading && !error && <CompactEvents events={data?.key_events} />}
    {hasEvents ? <details className="outlook-all-events"><summary>View all events</summary><OutlookEvents key={data?.ticker} intelligence={data?.event_intelligence} ticker={data?.ticker} /></details>
      : !loading && !error && <OutlookEvents key={data?.ticker} intelligence={data?.event_intelligence} ticker={data?.ticker} />}
    <p className="outlook-context-note">External context, not a trading recommendation.</p></section>;
}

const CATEGORIES = {
  company: "Company Outlook", earnings: "Earnings Outlook",
  industry: "Industry Outlook", economic: "Economic Outlook",
  market: "Market Outlook", geopolitical: "Geopolitical Outlook",
};
const STATES = {
  unavailable: "Unavailable", insufficient_data: "Insufficient data",
  error: "Temporarily unavailable", not_material: "Not Material",
  placeholder: "Not connected",
};

function classification(item) {
  return item?.status === "available" || item?.status === "partial"
    ? (typeof item.label === "string" ? item.label : "Unavailable")
    : STATES[item?.status] || "Unavailable";
}

function factorSources(category, factor) {
  const ids = new Set(factor.evidence_ids || []);
  return [...new Map((category.evidence || [])
    .filter((item) => ids.has(item.id))
    .map((item) => [`${item.raw_provider}:${item.id}`, item])).values()];
}

export function OutlookCategories({ categories }) {
  return (
    <div className="outlook-categories">
      {Object.entries(CATEGORIES).map(([key, title]) => {
        const category = categories?.[key];
        return (
          <section className="outlook-category" key={key}>
            <div className="panel-header"><h4>{title}</h4><span>{classification(category)}</span></div>
            <p>{category?.summary || "No evidence is available."}</p>
            {Array.isArray(category?.factors) && category.factors.length > 0 && (
              <ul>{category.factors.map((factor, index) => (
                <li key={`${factor.title}-${index}`}>
                  <strong>{factor.title}</strong>{factor.impact ? ` · ${factor.impact}` : ""}
                  <p>{factor.description}</p>
                  {factorSources(category, factor).map((item) => (
                    <small key={`${item.raw_provider}-${item.id}`}>
                      {typeof item.source_url === "string" && /^https?:\/\//.test(item.source_url)
                        ? <a href={item.source_url} target="_blank" rel="noopener noreferrer">Source: {item.source}</a>
                        : <>Source: {item.source}</>}
                      {" "}
                    </small>
                  ))}
                </li>
              ))}</ul>
            )}
          </section>
        );
      })}
    </div>
  );
}

export default function OutlookPanel({ data, loading = false, error = "", embedded = false }) {
  const label = loading ? "Loading…" : error ? "Temporarily unavailable" : classification(data);
  const summary = loading ? "Loading Outlook…" : error
    ? "Outlook is temporarily unavailable. Please try again later."
    : data?.summary || "Outlook data is unavailable.";
  const hasCategories = !loading && !error && data?.categories && typeof data.categories === "object";
  return (
    <details className={`${embedded ? "analysis-section" : "panel-box"} outlook-card`} aria-busy={loading}>
      <summary className="outlook-header">
        <div className="panel-header"><h3>Outlook</h3><span className="outlook-disclosure" aria-hidden="true">⌄</span></div>
        <div className="outlook-label">{label}</div>
        {data?.metadata?.uses_placeholder_data && !loading && !error && (
          <span className="partial-data-badge">Preview · Intelligence not connected</span>
        )}
        {!data?.metadata?.uses_placeholder_data && !loading && !error && Number.isInteger(data?.available_categories) && (
          <span className="partial-data-badge">{data.available_categories} of 6 Outlook categories available</span>
        )}
        <p className="outlook-summary">{summary}</p>
      </summary>
      {hasCategories ? <OutlookCategories categories={data.categories} /> : <p>{summary}</p>}
    </details>
  );
}

import { useEffect, useState } from "react";
import { safeSourceUrl } from "../utils/outlookPresentation";

function dateLabel(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? null : date.toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "numeric", timeZone: "UTC",
  });
}

function valueLabel(value) {
  if (!value) return "Unavailable";
  if (value.text) return value.text;
  if (Number.isFinite(value.lower) && Number.isFinite(value.upper)) {
    return `${value.lower.toFixed(2)}–${value.upper.toFixed(2)}${value.unit === "percent" ? "%" : ` ${value.unit}`}`;
  }
  if (!Number.isFinite(value.amount)) return "Unavailable";
  if (value.unit === "basis_points") return value.amount === 0 ? "Unchanged (0 bp)" : `${value.amount > 0 ? "+" : ""}${value.amount} bp`;
  return `${value.amount} ${value.unit}`;
}

function SourceLink({ source, children }) {
  const url = safeSourceUrl(source?.source_url);
  return url ? <a href={url} target="_blank" rel="noopener noreferrer">{children || source.source}</a> : <span>{children || source?.source}</span>;
}

function EventDetails({ item, ticker, now }) {
  const event = item.event;
  const expectation = event.expectation_status === "available" ? event.expectation : null;
  const cutoff = event.announced_at ? Date.parse(event.announced_at) : now;
  const fresh = expectation && Date.parse(expectation.expires_at) > cutoff
    && Date.parse(expectation.observed_at) <= cutoff
    && cutoff - Date.parse(expectation.observed_at) <= 86400000;
  return <div className="outlook-event-detail">
    <p>{event.summary}</p>
    <dl>
      {event.scheduled_date && <><dt>Scheduled</dt><dd>{dateLabel(event.scheduled_date)}</dd></>}
      {event.announced_at && <><dt>Announced</dt><dd>{new Date(event.announced_at).toLocaleString("en-US", { timeZone: "America/New_York", timeZoneName: "short" })}</dd></>}
      {event.previous_value && <><dt>Previous target</dt><dd>{valueLabel(event.previous_value)}</dd></>}
      {event.actual_value && <><dt>New target</dt><dd>{valueLabel(event.actual_value)}</dd></>}
      {event.change && <><dt>Change</dt><dd>{valueLabel(event.change)}</dd></>}
      {event.effective_date && <><dt>Effective</dt><dd>{dateLabel(event.effective_date)}</dd></>}
      {fresh && expectation.expected_value && <><dt>Expected {expectation.metric === "change" ? "change" : "outcome"}</dt><dd>{valueLabel(expectation.expected_value)}</dd></>}
      {fresh && ["as_expected", "different_from_expected"].includes(event.surprise?.status) && <>
        <dt>Surprise</dt><dd>{event.surprise.status === "as_expected" ? "As expected" : "Different from expected"}</dd>
      </>}
      {fresh && event.surprise?.status === "probability_based" && <>
        <dt>Surprise context</dt><dd>The actual outcome had {(event.surprise.actual_outcome_probability * 100).toFixed(0)}% probability before announcement.</dd>
      </>}
    </dl>
    {fresh && <div className="outlook-event-expectation">
      {expectation.outcomes?.length > 0 && <>
        <h5>Event outcome probabilities</h5>
        <ul>{expectation.outcomes.map((outcome) => <li key={outcome.title}>{outcome.title}: {(outcome.probability * 100).toFixed(0)}%</li>)}</ul>
        <p>These describe the policy outcome, not the stock’s reaction.</p>
      </>}
      <p>{expectation.basis === "market_implied" ? "Market-implied" : expectation.basis === "options_implied" ? "Options-implied" : "Structured consensus"}
        {event.announced_at ? " · Before announcement" : ""}</p>
      <p>Observed {new Date(expectation.observed_at).toLocaleString("en-US", { timeZone: "America/New_York", timeZoneName: "short" })}</p>
      <SourceLink source={expectation.provenance} />
    </div>}
    {!fresh && <p className="outlook-evidence-note">Expectations and surprise unavailable.</p>}
    <h5>Why this matters to {ticker}</h5>
    <p>{item.exposure.reason}</p>
    <p className="outlook-evidence-note">Stock direction is uncertain.</p>
    <div className="outlook-sources">
      <span>Sources</span>
      <ul>{event.provenance.map((source, index) => <li key={`${source.source_url}-${index}`}>
        <SourceLink source={source}>{source.source}{event.announced_at ? ` · ${dateLabel(event.announced_at)}` : ""}</SourceLink>
      </li>)}
        {item.exposure.link?.source_url && <li><SourceLink source={item.exposure.link}>{ticker} company profile</SourceLink></li>}
      </ul>
    </div>
  </div>;
}

export default function OutlookEvents({ intelligence, ticker }) {
  const [now, setNow] = useState(() => Date.now());
  const hasUpcomingExpectation = intelligence?.upcoming?.some((item) => item.event.expectation_status === "available");
  useEffect(() => {
    if (!hasUpcomingExpectation) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [hasUpcomingExpectation]);
  if (!intelligence) return null;
  const hasEvents = intelligence.upcoming?.length || intelligence.recent?.length;
  if (!hasEvents) return intelligence.status === "temporarily_unavailable"
    ? <p className="outlook-evidence-note" role="status">Event Intelligence is temporarily unavailable.</p> : null;
  return <section className="outlook-events" aria-label="Event Intelligence">
    <h4>Event Intelligence</h4>
    {[["upcoming", "Upcoming"], ["recent", "Recent"]].map(([key, title]) => intelligence[key]?.length > 0 && <div key={key}>
      <h5>{title}</h5>
      {intelligence[key].slice(0, 2).map((item) => <details className="outlook-event" key={item.event.event_id}>
        <summary>
          <span>{dateLabel(item.event.scheduled_date || item.event.announced_at)} · {item.event.title}</span>
          <span className="outlook-evidence-note">{item.event.status === "upcoming" ? "Scheduled" : valueLabel(item.event.change)}
            {item.event.status === "effective" ? " · Effective" : ""} · {item.exposure.relevance === "company_specific" ? "Company relevance" : "Broad context"}</span>
        </summary>
        <EventDetails item={item} ticker={ticker} now={now} />
      </details>)}
    </div>)}
  </section>;
}

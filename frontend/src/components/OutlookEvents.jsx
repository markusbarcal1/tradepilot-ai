import { Fragment, useEffect, useState } from "react";
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
  if (value.unit === "percent" || value.unit === "percent_saar") return `${value.amount}%${value.unit === "percent_saar" ? " annualized" : ""}`;
  if (value.unit === "jobs") return `${value.amount > 0 ? "+" : ""}${value.amount.toLocaleString("en-US")} jobs`;
  return `${value.amount} ${value.unit}`;
}

function freshExpectation(row, event, now) {
  const expectation = row.expectation_status === "available" ? row.expectation : null;
  const cutoff = event.announced_at ? Date.parse(event.announced_at) : now;
  return expectation && Date.parse(expectation.expires_at) > cutoff
    && Date.parse(expectation.observed_at) <= cutoff
    && cutoff - Date.parse(expectation.observed_at) <= 86400000 ? expectation : null;
}

function surpriseLabel(status) {
  return ({ as_expected: "As expected", different_from_expected: "Different from expected",
    higher_than_expected: "Higher than expected", lower_than_expected: "Lower than expected" })[status] || "Unavailable";
}

function periodLabel(period) {
  if (/^\d{4}-\d{2}$/.test(period)) return new Date(`${period}-01T00:00:00Z`).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
  if (/^\d{4}-Q[1-4]$/.test(period)) return `${period.slice(5)} ${period.slice(0, 4)}`;
  return period;
}

function SourceLink({ source, children }) {
  const url = safeSourceUrl(source?.source_url);
  return url ? <a href={url} target="_blank" rel="noopener noreferrer">{children || source.source}</a> : <span>{children || source?.source}</span>;
}

function EventDetails({ item, ticker, now }) {
  const event = item.event;
  const expectation = freshExpectation(event, event, now);
  const fresh = Boolean(expectation);
  return <div className="outlook-event-detail">
    <p>{event.summary}</p>
    <dl>
      {event.scheduled_date && <><dt>Scheduled</dt><dd>{dateLabel(event.scheduled_date)}</dd></>}
      {event.scheduled_at && <><dt>Release time</dt><dd>{new Date(event.scheduled_at).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/New_York", timeZoneName: "short" })}</dd></>}
      {event.reference_period && <><dt>Reference period</dt><dd>{periodLabel(event.reference_period)}</dd></>}
      {event.release_type && <><dt>Release type</dt><dd>{event.release_type}</dd></>}
      {event.announced_at && <><dt>Announced</dt><dd>{new Date(event.announced_at).toLocaleString("en-US", { timeZone: "America/New_York", timeZoneName: "short" })}</dd></>}
      {event.previous_value && <><dt>Previous target</dt><dd>{valueLabel(event.previous_value)}</dd></>}
      {event.actual_value && <><dt>New target</dt><dd>{valueLabel(event.actual_value)}</dd></>}
      {event.change && <><dt>Change</dt><dd>{valueLabel(event.change)}</dd></>}
      {event.effective_date && <><dt>Effective</dt><dd>{dateLabel(event.effective_date)}</dd></>}
      {event.measurements?.map((row) => {
        const expected = freshExpectation(row, event, now);
        if (!event.announced_at && !expected) return null;
        return <Fragment key={row.key}>
          <dt>{row.label}</dt><dd>
            {event.announced_at && <div>Actual: {valueLabel(row.actual_value)}</div>}
            {row.previous_value && <div>Previous estimate: {valueLabel(row.previous_value)}</div>}
            {expected?.expected_value && <div>Expected: {valueLabel(expected.expected_value)}</div>}
            {expected && <>
              <div>Observed {new Date(expected.observed_at).toLocaleString("en-US", { timeZone: "America/New_York", timeZoneName: "short" })}{event.announced_at ? " · Before announcement" : ""}</div>
              <SourceLink source={expected.provenance} />
            </>}
            {event.announced_at && expected && <div>Surprise: {surpriseLabel(row.surprise?.status)}</div>}
          </dd>
        </Fragment>;
      })}
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
    {!fresh && !event.measurements?.length && <p className="outlook-evidence-note">Expectations and surprise unavailable.</p>}
    {event.measurements?.length > 0 && !event.measurements.some((row) => freshExpectation(row, event, now)) && <p className="outlook-evidence-note">Consensus unavailable.</p>}
    {event.revisions?.length > 0 && <>
      <h5>Published revisions</h5>
      <ul>{event.revisions.map((revision, index) => <li key={`${revision.measurement_key}-${revision.reference_period}-${index}`}>
        {periodLabel(revision.reference_period)} · {event.measurements?.find((row) => row.key === revision.measurement_key)?.label || revision.measurement_key}: {valueLabel(revision.previous_value)} → {valueLabel(revision.actual_value)}. <SourceLink source={revision.provenance} />
      </li>)}</ul>
    </>}
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
  const hasUpcomingExpectation = intelligence?.upcoming?.some((item) => item.event.expectation_status === "available"
    || item.event.measurements?.some((row) => row.expectation_status === "available"));
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
      {intelligence[key].slice(0, 10).map((item) => <details className="outlook-event" key={item.event.event_id}>
        <summary>
          <span>{dateLabel(item.event.scheduled_date || item.event.announced_at)} · <strong>{item.event.title}</strong></span>
          <span className="outlook-evidence-note">{item.event.status === "upcoming" ? "Scheduled" : item.event.change ? valueLabel(item.event.change) : "Released"}
            {item.event.status === "upcoming" && item.event.scheduled_at ? ` · ${new Date(item.event.scheduled_at).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/New_York", timeZoneName: "short" })}` : ""}
            {item.event.status === "effective" ? " · Effective" : ""} · {item.exposure.relevance === "company_specific" ? "Company relevance" : "Broad context"}</span>
        </summary>
        <EventDetails item={item} ticker={ticker} now={now} />
      </details>)}
    </div>)}
  </section>;
}

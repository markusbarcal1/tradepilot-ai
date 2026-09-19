// Offline presentation fixture. Rates/dates mirror frozen Fed facts; exposure is synthetic.
const source = { source: "Federal Reserve — FOMC Statement", source_url: "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm" };
const exposure = { relevance: "company_specific", reason: "The company description explicitly identifies Bitcoin mining. Monetary policy can affect relevant financial conditions; stock direction is uncertain.",
  link: { source_url: "https://finance.yahoo.com/quote/ABTC/profile/" } };
export const eventFixture = {
  status: "available",
  upcoming: [{ exposure, directional_evidence: false, event: {
    event_id: "fomc:2026-10-28", title: "FOMC Rate Decision", status: "upcoming", scheduled_date: "2026-10-28",
    summary: "Scheduled FOMC meeting decision date; meeting dates may be revised.", expectation_status: "unavailable",
    provenance: [{ source: "Federal Reserve — FOMC Calendar", source_url: "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm" }],
  } }],
  recent: [{ exposure, directional_evidence: false, event: {
    event_id: "fomc:2026-09-16", title: "FOMC Rate Decision", status: "effective", scheduled_date: "2026-09-16",
    announced_at: "2026-09-16T18:00:00Z", effective_date: "2026-09-17", summary: "The Federal Reserve announced its target federal funds range decision.",
    previous_value: { lower: 3.5, upper: 3.75, unit: "percent" }, actual_value: { lower: 3.75, upper: 4, unit: "percent" },
    change: { amount: 25, unit: "basis_points" }, expectation_status: "unavailable", surprise: { status: "unavailable" },
    provenance: [source],
  } }],
};

export const probabilityFixture = {
  snapshot_id: "synthetic-consensus", event_id: "fomc:2026-09-16", metric: "change", basis: "market_implied",
  observed_at: "2026-09-16T16:00:00Z", expires_at: "2026-09-16T19:00:00Z",
  expected_value: { amount: 25, unit: "basis_points" },
  outcomes: [{ title: "Hold", probability: .3 }, { title: "+25 bp", probability: .7 }],
  provenance: { source: "Synthetic probability fixture", source_url: "https://example.com/probability-fixture" },
};

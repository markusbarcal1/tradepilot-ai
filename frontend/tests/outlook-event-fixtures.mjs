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

const issuerExposure = { relevance: "company_specific", reason: "This is NVIDIA Corporation's own earnings release, so relevance to NVDA is direct.",
  link: { source_url: "https://finance.yahoo.com/quote/NVDA/profile/" } };
export const earningsFixture = {
  status: "available",
  upcoming: [{ exposure: issuerExposure, directional_evidence: false, event: {
    event_id: "earnings:NVDA:next", event_type: "earnings_release", ticker: "NVDA", issuer: "NVIDIA Corporation",
    title: "NVDA Earnings", summary: "Provider-reported upcoming issuer earnings date.", status: "upcoming",
    scheduled_date: "2026-10-20", scheduled_at: "2026-10-20T16:05:00-04:00", schedule_certainty: "provider_reported",
    market_session: "after_market", measurements: [], expectation_status: "unavailable",
    provenance: [{ source: "Yahoo Finance — Earnings Calendar", source_url: "https://finance.yahoo.com/calendar/earnings?symbol=NVDA" }],
  } }],
  recent: [{ exposure: issuerExposure, directional_evidence: false, event: {
    event_id: "earnings:NVDA:FY2026:Q2", underlying_event_id: "earnings:NVDA:FY2026:Q2",
    event_type: "earnings_release", ticker: "NVDA", issuer: "NVIDIA Corporation", title: "NVDA Earnings",
    summary: "Issuer results for FY2026 Q2.", status: "occurred", scheduled_date: "2026-08-20",
    announced_at: "2026-08-20T20:05:00Z", reference_period: "FY2026 Q2", release_type: "Earnings release",
    reporting_identity: { status: "authoritative", periods: [{ ticker: "NVDA", fiscal_year: 2026, fiscal_period: "Q2", period_end: "2026-07-27" }] },
    guidance_status: "raised", expectation_status: "unavailable", surprise: { status: "unavailable" },
    measurements: [
      { key: "revenue", label: "Revenue", actual_value: { amount: 30.04, unit: "USD_billion" }, expectation_status: "unavailable", surprise: { status: "unavailable" } },
      { key: "diluted_eps", label: "Diluted EPS", actual_value: { amount: .67, unit: "USD_per_share" }, expectation_status: "unavailable", surprise: { status: "unavailable" } },
      { key: "gross_margin", label: "Gross Margin", actual_value: { amount: 75.1, unit: "percent" }, previous_value: { amount: 70.1, unit: "percent" }, expectation_status: "unavailable", surprise: { status: "unavailable" } },
    ],
    provenance: [{ source: "NVIDIA Corporation FY2026 Q2 Earnings Release", source_url: "https://www.sec.gov/Archives/nvda-exhibit.htm" }],
  } }],
};
